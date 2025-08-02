import requests
from agents.mlsysops.logger_util import logger

url = "http:///model/get/"

payload = {}
headers = {
  'accept': 'application/json'
}

response = requests.request("GET", url, headers=headers, data=payload)

logger.info(response.text)
