import pandas as pd
from sqlalchemy import text
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv(override=True)

# Database config
db_config = {
    "DB_DRIVER": "postgresql+psycopg2",  # e.g. postgresql+asyncpg
    "DB_USER": os.getenv("POSTGRES_USER"),
    "DB_PASSWORD": os.getenv("POSTGRES_PASSWORD"),
    "DB_HOST": "localhost",
    "DB_PORT": os.getenv("DB_PORT"),
    "DB_NAME": os.getenv("POSTGRES_DB")
}

# Build connection string
DATABASE_URL = (
    f"{db_config['DB_DRIVER']}://{db_config['DB_USER']}:{db_config['DB_PASSWORD']}"
    f"@{db_config['DB_HOST']}:{db_config['DB_PORT']}/{db_config['DB_NAME']}"
)
print(f"Connecting to database at {DATABASE_URL}")
"""# Create async engine and session
engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)

# Main async logic
async def insert_drift_metrics():
    df = pd.read_csv("drift_metrics_mmd.csv")

    # Add required fields
    df["rowid"] = [str(uuid.uuid4()) for _ in range(len(df))]
    df["timestamp"] = datetime.utcnow()

    async with AsyncSessionLocal() as session:
        for _, row in df.iterrows():
            await session.execute(text(""
                INSERT INTO drift_metrics (
                    rowid, feature, type, statistic, p_value,
                    method, drift_detected, timestamp, modelid
                ) VALUES (
                    :rowid, :feature, :type, :statistic, :p_value,
                    :method, :drift_detected, :timestamp, :modelid
                )
            ""), {
                "rowid": row["rowid"],
                "feature": row["feature"],
                "type": row["type"],
                "statistic": float(row["statistic"]),
                "p_value": float(row["p_value"]),
                "method": row["method"],
                "drift_detected": str(row["drift_detected"]),
                "timestamp": row["timestamp"],
                "modelid": row["modelid"]
            })
        await session.commit()

# Entry point
if __name__ == "__main__":
    asyncio.run(insert_drift_metrics())
"""