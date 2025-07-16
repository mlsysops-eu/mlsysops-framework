import os

# Fetching environment variables with default values if not set
redis_host = os.getenv('REDIS_HOST', '172.25.27.72')  # Default to '10.96.12.155'
redis_port = int(os.getenv('REDIS_PORT', 6379))  # Default to 6379
redis_db_number = int(os.getenv('REDIS_DB_NUMBER', 0))  # Default to 0
redis_password = os.getenv('REDIS_PASSWORD', 'secret')  # Uncomment if password is needed
redis_queue_name = os.getenv('REDIS_QUEUE_NAME', 'valid_descriptions_queue')  # Default queue name
redis_channel_name = os.getenv('REDIS_CHANNEL_NAME', 'my_channel')  # Default channel name
redis_dict_name = os.getenv('REDIS_DICT_NAME', 'system_app_hash')  # Default dictionary name
redis_dict2_name = os.getenv('REDIS_DICT2_NAME', 'component_metrics')  # Components hash
redis_ml_queue = os.getenv('REDIS_ML_QUEUE_NAME', 'ml_deployment_queue')  # Default channel name ""
