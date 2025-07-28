import boto3
from botocore.exceptions import NoCredentialsError, ClientError
from botocore.config import Config
from boto3.exceptions import S3UploadFailedError
from dotenv import load_dotenv
import os
import logging
from agents.mlsysops.logger_util import logger

load_dotenv(verbose=True, override=True,dotenv_path='./param.env')

class S3Manager:
    def __init__(self, bucket_name, aws_access_key_id, aws_secret_access_key, endpoint_url):
        """
        Initialize the S3Manager with a bucket name and optional AWS credentials.
        """
        self.bucket_name = bucket_name
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            endpoint_url=endpoint_url,
            config=Config(s3={'addressing_style': 'path', 'payload_signing_enabled': False})
        )
        self._ensure_bucket_exists()

    def _ensure_bucket_exists(self):
        """
        Check if the bucket exists. If not, create it.
        """
        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            logger.info(f"Bucket '{self.bucket_name}' already exists.")
        except ClientError as e:
            # If a 404 error is thrown, then the bucket does not exist.
            error_code = int(e.response['Error']['Code'])
            if error_code == 404:
                try:
                    self.s3_client.create_bucket(Bucket=self.bucket_name)
                    logger.info(f"Bucket '{self.bucket_name}' created successfully.")
                except ClientError as ce:
                    logger.error("Error creating bucket:", ce)
            else:
                logger.error("Error checking bucket:", e)

    def upload_file(self, file_name, object_name=None):
        """Upload a file to an S3 bucket

        :param file_name: File to upload
        :param bucket: Bucket to upload to
        :param object_name: S3 object name. If not specified then file_name is used
        :return: True if file was uploaded, else False
        """

        # If S3 object_name was not specified, use file_name
        if object_name is None:
            object_name = os.path.basename(file_name)
        try:
            with open(file_name, 'rb') as f:
                data = f.read()
                self.s3_client.put_object(Bucket=self.bucket_name, Key=object_name, Body=data, ContentLength=len(data))
        except ClientError as e:
            logging.error(e)
            return False
        return True


    def download_file(self, object_name, download_path):
        """
        Download a file from the bucket.
        
        :param object_name: Name of the file in S3.
        :param download_path: Local path where the file will be saved.
        """
        try:
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=object_name)
            body = response['Body'].read()
            with open(download_path, 'wb') as f:
                f.write(body)
            logger.info(f"File '{object_name}' downloaded from bucket '{self.bucket_name}' to '{download_path}'.")
        except ClientError as e:
            logger.info("Error downloading file:", e)

    def delete_file(self, object_name):
        """
        Delete a file from the bucket.
        
        :param object_name: Name of the file in S3 to delete.
        """
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=object_name)
            logger.info(f"File '{object_name}' deleted from bucket '{self.bucket_name}'.")
        except ClientError as e:
            logger.error("Error deleting file:", e)
    
    def list_files(self):
        """
        List all files in the bucket.
        """
        try:
            response = self.s3_client.list_objects_v2(Bucket=self.bucket_name)
            if 'Contents' in response:
                files = [obj['Key'] for obj in response['Contents']]
                logger.info("Files in bucket:")
                for f in files:
                    logger.debug(" -", f)
                return files
            else:
                logger.warning("No files found in bucket.")
                return []
        except ClientError as e:
            logger.error("Error listing files:", e)
            return []

# Example usage:
if __name__ == "__main__":
    manager = S3Manager(
            os.getenv("AWS_S3_BUCKET_DATA"),
            os.getenv("AWS_ACCESS_KEY_ID"),
            os.getenv("AWS_SECRET_ACCESS_KEY"),
            os.getenv("AWS_ACCESS_URL")
        )
    # Upload a file
    #manager.list_files()
    # manager.upload_file('model_backend_id_39.pkl')
    
    manager.list_files()
    # Download the file
    manager.download_file('9ce175cf-5fa8-4c72-ac30-15467a75dd98.csv', '9ce175cf-5fa8-4c72-ac30-15467a75dd98.csv')
    
    # Delete the file
    #manager.delete_file('c2377cdc-e8ba-4cf0-9392-80c0983f0b4d.pkl')
    #manager.delete_file('c2377cdc-e8ba-4cf0-9392-80c0983f0b4d.py')
    #manager.delete_file('c2377cdc-e8ba-4cf0-9392-80c0983f0b4d.csv')
    
    #manager.list_files()
    # Download the file
    #manager.download_file('sample_data.csv', 'downloaded_example.csv')
