import boto3


class S3Persistence(object):
    def __init__(self, s3_config: dict) -> None:
        session = boto3.session.Session(aws_access_key_id=s3_config['access_key_id'],
                                        aws_secret_access_key=s3_config['secret_access_key'])
        self.s3 = session.resource('s3', endpoint_url='https://{}'.format(s3_config['host']))
        self.bucket = s3_config['bucket']

    def save_to_s3(self, key: str, byte_string: bytes) -> None:
        self.s3.Object(self.bucket, key).put(Body=byte_string)

    def load_from_s3(self, key: str) -> bytes:
        loaded_object = self.s3.Object(self.bucket, key).get()
        return loaded_object['Body'].read()

