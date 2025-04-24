
# !/usr/bin/python3
# Author John Byabazaire

from dotenv import load_dotenv
import os
import asyncio_redis
#import redis


load_dotenv(verbose=True, override=True)

async def create_redis_connection():
    try:
        # Initialize Redis connection using asyncio-redis
        redis_client = await asyncio_redis.Connection.create(
            host=os.getenv('REDIS_HOST'),
            port=int(os.getenv('REDIS_PORT')),
            password=os.getenv('REDIS_HOST_PASSWORD'),
            db=int(os.getenv('REDIS_DB_NUMBER'))
        )
        
        # Ping the Redis server
        #ping = await redis_client.ping()  # Awaiting the ping
        if await redis_client.ping():
            print(f"Successfully connected to Redis at {os.getenv('REDIS_HOST')}.")
            return redis_client
        else:
            raise Exception("Could not connect to Redis.")
    except Exception as e:
        print(f"Redis connection error: {e}")
        raise