import os
import sys
from mle_connector import MLEConnector
from s3_persistence import S3Persistence
from train_score_helper import TrainScoreHelper
import json
from datetime import datetime, timedelta, tzinfo
import pickle
import threading
import pandas as pd

s3 = S3Persistence(json.loads(os.environ['S3_KEY']))
train_score_helper = TrainScoreHelper()


def fix_java_path():
    """
    Because of missing privileges, the apt-buildpack is not able to add the java bin directory to the PATH.
    This code adds the missing folder to the PATH environment variable
    """
    os.environ['PATH'] = os.environ['PATH'] + ":/home/vcap/deps/0/apt/usr/lib/jvm/java-8-openjdk-amd64/jre/bin"


def fix_java_certificates():
    """
    The java installation does not contain any root ssl certificates,
    therefore we have to import them manually into the cacerts file.
    """
    os.remove('/home/vcap/deps/0/apt/usr/lib/jvm/java-8-openjdk-amd64/jre/lib/security/cacerts')
    os.system(
        'echo "" | openssl s_client -connect authentication.eu10.hana.ondemand.com:443 -showcerts 2>/dev/null | openssl x509 -out /home/vcap/certfile.txt')
    os.system(
        '/home/vcap/deps/0/apt/usr/lib/jvm/java-8-openjdk-amd64/jre/bin/keytool -import -alias ca -file /home/vcap/certfile.txt -keystore /home/vcap/deps/0/apt/usr/lib/jvm/java-8-openjdk-amd64/jre/lib/security/cacerts -storepass changeit -noprompt')
    os.remove('/home/vcap/certfile.txt')


def get_dataset() -> dict:
    """
    Requesting Indicator ROTATIONAL_SPEED from Indicator Group PUMP_TAGS attached to
    equipment model with id 6B445BCEC6A14F38A7FB8211C42FB599
    aggregated to Maximum Value of 2 Minutes Windows
    """
    return {
        "name": "",
        "description": "",
        "equipmentModelName": "",
        "equipmentModelId": "6B445BCEC6A14F38A7FB8211C42FB599",
        "nullValueStrategy": "Ignore",
        "features": [
            {'indicatorGroup': 'PUMP_TAGS', 'indicator': 'ROTATIONAL_SPEED', 'aggregateFunction': 'MAX',
             'bucketSizeMultiple': 1, 'bucketOffsetMultiple': 0}
        ],
        "duration": "PT2M"
    }


def get_model_key() -> str:
    return 'blog-post/model1.raw'


def train():
    """
    Function triggers training of model and saves model to s3
    """
    print("Starting Training")
    data = get_training_data()
    model = train_score_helper.train(data)
    s3.save_to_s3(get_model_key(), pickle.dumps(model))
    print("Finished Training")


def score(minutes_back: int = 1440, schedule_configuration: dict = {"active": False, "interval": 2}):
    """
    Function triggers scoring of new data
    """
    print("Starting Scoring")
    print("Loading model '{}' from s3".format(get_model_key()))
    model = pickle.loads(s3.load_from_s3(get_model_key()))
    print("Collecting data of the last {} minute(s)".format(minutes_back))
    data = get_scoring_data(minutes_back=minutes_back)
    print("Collected {} rows of data for scoring".format(len(data)))
    if len(data) == 0:
        print("Skipping scoring and persisting of scores.")
    else:
        scores = train_score_helper.score(data, model)

        mapping = [
            {
                "name": "score",
                "Indicator": "Anomaly_Score",
                "IndicatorGroup": "Scores"
            }
        ]
        print("Persisting {} rows of data into indicator '{}'".format(len(scores), mapping[0]['Indicator']))
        mle.persist(scores, mapping)
        print("Persisted {} rows of data into indicator '{}'".format(len(scores), mapping[0]['Indicator']))
    print("Finished Scoring")
    if schedule_configuration['active']:
        print("Scheduling to run scoring again in {} seconds".format(schedule_configuration['interval'] * 60))
        threading.Timer(schedule_configuration['interval'] * 60, score, kwargs={"minutes_back": minutes_back,
                                                                                "schedule_configuration": schedule_configuration}).start()


def get_training_data(from_date: str = "2019-04-01T00:00:00Z", to_date: str = "2019-04-20T00:00:00Z") -> pd.DataFrame:
    print("Collecting data from '{}' to '{}'".format(from_date, to_date))
    return mle.collect(ts_from=from_date, ts_to=to_date, dataset=get_dataset(), equipment="2828273CC809415D923E5FBF24542AAF")


def get_scoring_data(minutes_back: int = 1) -> pd.DataFrame:
    to_date = datetime.utcnow()
    from_date = to_date - timedelta(minutes=minutes_back)
    print("Collecting data from '{}' to '{}'".format(from_date, to_date))
    df = mle.collect(ts_from=from_date.isoformat(), ts_to=to_date.isoformat(), dataset=get_dataset(),
                     equipment="2828273CC809415D923E5FBF24542AAF")
    if len(df) == 0:
        print('Received no data for scoring.')
    else:
        print("Received data from '{}' to '{}'".format(df.Timestamp[0], df.Timestamp[len(df) - 1]))
    return df


def init_connector() -> MLEConnector:
    if 'VCAP_APPLICATION' in os.environ:
        print('Running on Cloud Foundry. Fixing java path and java ssl certificates')
        fix_java_path()
        fix_java_certificates()
        jar_path = '/home/vcap/app/' + [x for x in os.listdir('/home/vcap/app') if 'jar' in x][0]
    else:
        print('Running in local development mode.')
        jar_path = [x for x in os.listdir('.') if 'jar' in x][0]

    print("Using jar: {}".format(jar_path))
    return MLEConnector(jar_path, asset_central_credentials=os.environ['AC_KEY'],
                        iot_ae_credentials=os.environ['IOT_KEY'])


if __name__ == '__main__':
    mle = init_connector()
    if len(sys.argv) <= 1:
        print('Please provide argument train or score')
        exit(1)
    if sys.argv[1] == 'train':
        train()
    elif sys.argv[1] == 'score':
        score()
    elif sys.argv[1] == 'score-scheduled':
        score(minutes_back=10, schedule_configuration={"active": True, "interval": 2})
    else:
        print('Please provide argument train or score')
        exit(1)
