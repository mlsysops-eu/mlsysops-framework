#  Copyright (c) 2025. MLSysOps Consortium
#  #
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#  #
#      http://www.apache.org/licenses/LICENSE-2.0
#  #
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

import pandas
import pandas as pd
import asyncio
import time


@dataclass
class MonitorData:
    """
    MonitorData is a thread-safe container that provides mechanisms to store, manage, and query time-series data.

    This class is designed to handle a dataset where entries include a timestamp field. It supports dynamic addition
    of new columns, removal of outdated records based on a maximum age limit, and querying data based on a time range
    or fetching the latest entry. The operations on the data store are protected by an asyncio lock to ensure concurrency
    safety in asynchronous environments.

    Attributes:
        max_age (int): The maximum age (in seconds) for an entry to remain in the data store. Older entries are removed.
        data_store (pd.DataFrame): A pandas DataFrame serving as the main storage for entries. Each entry must include a
            `timestamp` field.
        _lock (asyncio.Lock): An asyncio lock object used to enforce thread-safety when accessing or modifying the
            data store.
    """
    max_age: int = 30
    data_store: pd.DataFrame = field(default_factory=lambda: pd.DataFrame(columns=["timestamp"]))
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)

    async def add_entry(self, entry: Dict[str, Any]) -> None:
        """
        Add an entry to the MonitorData's storage. If a row with the same timestamp exists,
        update that row with the new entry. Otherwise, create a new row.
        This method ensures thread-safety using an asyncio lock.
        """
        async with self._lock:
            current_time = time.time()
            # Add missing columns dynamically
            for column in entry.keys():
                if column not in self.data_store.columns:
                    self.data_store[column] = None  # Add the new column with default `None` values

            # Check if a row with the same timestamp already exists
            timestamp_match = self.data_store["timestamp"] == entry["timestamp"]
            if timestamp_match.any():
                # If a row with the same timestamp exists, update that row's values
                for column, value in entry.items():
                    self.data_store.loc[timestamp_match, column] = value
            else:
                # If no such row exists, append the new row
                new_row = pd.DataFrame([entry])
                self.data_store = pd.concat([self.data_store, new_row], ignore_index=True)

            # Clean up old data outside the `max_age`
            self.data_store = self.data_store[self.data_store["timestamp"] > current_time - self.max_age]

    async def get_data(self) -> pd.DataFrame:
        df = None
        async with self._lock:
            df = pandas.DataFrame(self.data_store)

        return df

    async def query_data(self, start_time: float = None, end_time: float = None, latest: bool = False) -> pd.DataFrame:
        """
        Query data within a given time range, fetch the latest row, or fetch everything if no time range is provided.

        :param start_time: The start time for the query (timestamp).
        :param end_time: The end time for the query (timestamp).
        :param latest: If True, fetch the latest row from the data store.
        :return: A filtered DataFrame containing data within the time range, the latest row, or all data.
        """
        async with self._lock:
            if latest:
                # Fetch the latest row based on the 'timestamp' column
                if not self.data_store.empty:
                    latest_row = self.data_store.iloc[-1:]  # Using iloc to fetch the last row
                    return latest_row
                else:
                    raise ValueError("The data store is empty. No latest row available.")

            # If both start_time and end_time are None, return the entire dataset
            if start_time is None and end_time is None:
                return self.data_store

            # Ensure both start_time and end_time are provided when querying a range
            if start_time is None or end_time is None:
                raise ValueError(
                    "Both start_time and end_time must be provided when not fetching the latest row or all data.")

            # Query data within the specified time range
            return self.data_store[
                (self.data_store["timestamp"] >= start_time) & (self.data_store["timestamp"] <= end_time)
                ]