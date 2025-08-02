#!/usr/bin/python3
# Author: John Byabazaire

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import os
from agents.mlsysops.logger_util import logger

load_dotenv(verbose=True, override=True)

db_config = {
    "DB_DRIVER": os.getenv("DB_DRIVER"), 
    "DB_USER": os.getenv("POSTGRES_USER"), 
    "DB_PASSWORD": os.getenv("POSTGRES_PASSWORD"),
    "DB_HOST": os.getenv("DB_HOST_NAME"),
    "DB_PORT": os.getenv("DB_PORT"),
    "DB_NAME": os.getenv("POSTGRES_DB")
}


SQLALCHEMY_DATABASE_URL = (
    f"{db_config['DB_DRIVER']}://{db_config['DB_USER']}:"
    f"{db_config['DB_PASSWORD']}@{db_config['DB_HOST']}:"
    f"{db_config['DB_PORT']}/{db_config['DB_NAME']}"
)

engine = create_async_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={}, future=True
)

SessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False, future=True
)

Base = declarative_base()

async def get_db():
    async with SessionLocal() as db:
        try:
            yield db
            await db.commit()  # Commit transaction
        except Exception as e:
            await db.rollback()  # Rollback in case of error
            logger.error(f"Error in database transaction: {e}")
            raise
