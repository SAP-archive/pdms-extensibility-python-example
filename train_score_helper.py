import pandas
import numpy as np
from sklearn.neighbors import KernelDensity

class TrainScoreHelper(object):
    def __init__(self):
        pass

    def train(self, df: pandas.DataFrame) -> dict:
        """
        Trains gaussian KernelDensity estimator from sklearn package to monitor the rotational speed of the pump
        :param df: input data
        :return: model object
        """
        kde = KernelDensity(kernel='gaussian', bandwidth=0.75).fit(df["PUMP_TAGS.ROTATIONAL_SPEED_MAX"].values.reshape(-1, 1))
        return {'model': kde}

    def score(self, df: pandas.DataFrame, model) -> pandas.DataFrame:
        """
        Scores new data with trained model. Returns dataFrame with scores, the higher the score, the higher the anomaly
        in the data compared to the training data.
        :param df: input data
        :param model: model object
        :return: score data
        """
        scores = df.copy()
        model = model['model']
        print("Scoring {} rows of data".format(len(scores)))
        scores['score'] = np.clip(-model.score_samples(scores[['PUMP_TAGS.ROTATIONAL_SPEED_MAX']].values.reshape(-1, 1)),
                                  a_min=0, a_max=1000)
        feature_columns_to_delete = list(set(scores.columns) - set(['Equipment', 'EquipmentModel', 'Timestamp', 'score']))
        scores.drop(feature_columns_to_delete, axis=1, inplace=True)
        return scores
