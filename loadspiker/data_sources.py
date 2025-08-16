"""
Data source management for LoadSpiker load testing
Supports CSV, JSON, and other data formats for data-driven testing
"""

import csv
import json
import random
import threading
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Union
from enum import Enum


class DataStrategy(Enum):
    """Data distribution strategies"""
    SEQUENTIAL = "sequential"
    RANDOM = "random"
    CIRCULAR = "circular" 
    UNIQUE = "unique"
    SHARED = "shared"


class DataSource(ABC):
    """Abstract base class for data sources"""
    
    def __init__(self, name: str = "data"):
        self.name = name
        self.data: List[Dict[str, Any]] = []
        self.loaded = False
        
    @abstractmethod
    def load_data(self) -> List[Dict[str, Any]]:
        """Load data from source"""
        pass
        
    @abstractmethod
    def validate_data(self) -> bool:
        """Validate data integrity"""
        pass
        
    def get_row_count(self) -> int:
        """Get number of data rows"""
        return len(self.data)
        
    def get_columns(self) -> List[str]:
        """Get column names"""
        if not self.data:
            return []
        return list(self.data[0].keys())


class CSVDataSource(DataSource):
    """CSV file data source"""
    
    def __init__(self, file_path: str, name: str = "data", 
                 encoding: str = "utf-8", delimiter: str = ",",
                 skip_empty_rows: bool = True):
        super().__init__(name)
        self.file_path = file_path
        self.encoding = encoding
        self.delimiter = delimiter
        self.skip_empty_rows = skip_empty_rows
        
    def load_data(self) -> List[Dict[str, Any]]:
        """Load data from CSV file"""
        try:
            with open(self.file_path, 'r', encoding=self.encoding, newline='') as csvfile:
                # Detect delimiter if not specified
                if self.delimiter == "auto":
                    sample = csvfile.read(1024)
                    csvfile.seek(0)
                    sniffer = csv.Sniffer()
                    self.delimiter = sniffer.sniff(sample).delimiter
                
                reader = csv.DictReader(csvfile, delimiter=self.delimiter)
                self.data = []
                
                for row_num, row in enumerate(reader, 1):
                    # Skip empty rows if configured
                    if self.skip_empty_rows and not any(row.values()):
                        continue
                        
                    # Convert data types
                    processed_row = self._process_row(row, row_num)
                    self.data.append(processed_row)
                
                self.loaded = True
                return self.data
                
        except FileNotFoundError:
            raise FileNotFoundError(f"CSV data file not found: {self.file_path}")
        except csv.Error as e:
            raise ValueError(f"CSV parsing error in {self.file_path}: {e}")
        except UnicodeDecodeError as e:
            raise ValueError(f"Encoding error in {self.file_path}: {e}. Try different encoding.")
            
    def _process_row(self, row: Dict[str, str], row_num: int) -> Dict[str, Any]:
        """Process and convert row data types"""
        processed = {}
        
        for key, value in row.items():
            # Clean up key names
            clean_key = key.strip()
            
            # Convert value types
            if value == "":
                processed[clean_key] = None
            elif value.lower() in ("true", "false"):
                processed[clean_key] = value.lower() == "true"
            elif value.isdigit():
                processed[clean_key] = int(value)
            else:
                # Try to convert to float
                try:
                    if '.' in value:
                        processed[clean_key] = float(value)
                    else:
                        processed[clean_key] = value
                except ValueError:
                    processed[clean_key] = value
                    
        # Add metadata
        processed['_row_number'] = row_num
        return processed
        
    def validate_data(self) -> bool:
        """Validate CSV data"""
        if not self.loaded:
            self.load_data()
            
        if not self.data:
            raise ValueError(f"No data loaded from {self.file_path}")
            
        # Check for consistent columns
        if len(self.data) > 1:
            first_keys = set(self.data[0].keys())
            for i, row in enumerate(self.data[1:], 1):
                if set(row.keys()) != first_keys:
                    raise ValueError(f"Inconsistent columns in row {i+1} of {self.file_path}")
                    
        return True


class DataDistributor:
    """Manages data distribution to virtual users"""
    
    def __init__(self, data_source: DataSource, strategy: DataStrategy = DataStrategy.SEQUENTIAL):
        self.data_source = data_source
        self.strategy = strategy
        self.current_index = 0
        self.used_indices = set()
        self.lock = threading.Lock()
        
        # Load and validate data
        if not data_source.loaded:
            data_source.load_data()
        data_source.validate_data()
        
    def get_data_for_user(self, user_id: int) -> Dict[str, Any]:
        """Get data row for specific user"""
        with self.lock:
            data_count = self.data_source.get_row_count()
            
            if data_count == 0:
                raise ValueError("No data available")
                
            if self.strategy == DataStrategy.SEQUENTIAL:
                index = user_id % data_count
                
            elif self.strategy == DataStrategy.RANDOM:
                index = random.randint(0, data_count - 1)
                
            elif self.strategy == DataStrategy.CIRCULAR:
                index = self.current_index % data_count
                self.current_index += 1
                
            elif self.strategy == DataStrategy.UNIQUE:
                if len(self.used_indices) >= data_count:
                    raise ValueError("No more unique data available")
                    
                # Find unused index
                available_indices = set(range(data_count)) - self.used_indices
                index = min(available_indices)  # Take first available
                self.used_indices.add(index)
                
            elif self.strategy == DataStrategy.SHARED:
                # All users get the same first row
                index = 0
                
            else:
                raise ValueError(f"Unknown data strategy: {self.strategy}")
                
            return self.data_source.data[index].copy()
            
    def get_stats(self) -> Dict[str, Any]:
        """Get distribution statistics"""
        return {
            "total_rows": self.data_source.get_row_count(),
            "strategy": self.strategy.value,
            "used_indices_count": len(self.used_indices),
            "columns": self.data_source.get_columns()
        }


class DataManager:
    """Central manager for multiple data sources"""
    
    def __init__(self):
        self.data_sources: Dict[str, DataDistributor] = {}
        self.default_source_name = "data"
        
    def add_csv_source(self, file_path: str, name: str = None, 
                      strategy: DataStrategy = DataStrategy.SEQUENTIAL,
                      **csv_options) -> None:
        """Add CSV data source"""
        source_name = name or self.default_source_name
        
        csv_source = CSVDataSource(file_path, source_name, **csv_options)
        distributor = DataDistributor(csv_source, strategy)
        
        self.data_sources[source_name] = distributor
        
    def get_user_data(self, user_id: int, source_name: str = None) -> Dict[str, Any]:
        """Get data for user from specified source"""
        source_name = source_name or self.default_source_name
        
        if source_name not in self.data_sources:
            raise ValueError(f"Data source '{source_name}' not found")
            
        return self.data_sources[source_name].get_data_for_user(user_id)
        
    def get_all_user_data(self, user_id: int) -> Dict[str, Dict[str, Any]]:
        """Get data from all sources for user"""
        all_data = {}
        
        for source_name, distributor in self.data_sources.items():
            all_data[source_name] = distributor.get_data_for_user(user_id)
            
        return all_data
        
    def list_sources(self) -> List[str]:
        """List all loaded data source names"""
        return list(self.data_sources.keys())
        
    def get_source_info(self, source_name: str = None) -> Dict[str, Any]:
        """Get information about data source"""
        source_name = source_name or self.default_source_name
        
        if source_name not in self.data_sources:
            raise ValueError(f"Data source '{source_name}' not found")
            
        distributor = self.data_sources[source_name]
        return distributor.get_stats()
        
    def clear_sources(self) -> None:
        """Clear all data sources"""
        self.data_sources.clear()


# Global instance for easy access
_global_data_manager = DataManager()

# Convenience functions
def load_csv_data(file_path: str, name: str = "data", 
                 strategy: str = "sequential", **options) -> None:
    """Load CSV data file"""
    strategy_enum = DataStrategy(strategy.lower())
    _global_data_manager.add_csv_source(file_path, name, strategy_enum, **options)

def get_user_data(user_id: int, source_name: str = None) -> Dict[str, Any]:
    """Get data for user"""
    return _global_data_manager.get_user_data(user_id, source_name)

def get_data_manager() -> DataManager:
    """Get global data manager instance"""
    return _global_data_manager
