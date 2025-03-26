"""
SQLite connection pool implementation for the Discord bot
This module helps prevent database locking issues by managing connections efficiently
"""

import aiosqlite
import asyncio
import contextlib
import time
import logging
from typing import Dict, List, Optional, Any

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('db_pool')

class DatabasePool:
    """A simple connection pool for SQLite to avoid database locking issues"""
    
    def __init__(self, database_path: str, max_connections: int = 5, timeout: float = 30.0):
        self.database_path = database_path
        self.max_connections = max_connections
        self.timeout = timeout
        self.connections: List[aiosqlite.Connection] = []
        self.available: List[bool] = []
        self.connection_locks: List[asyncio.Lock] = []
        self.pool_lock = asyncio.Lock()
        self.initialized = False
        self.stats: Dict[str, int] = {
            "connections_created": 0,
            "connections_used": 0,
            "connection_wait_time": 0,
            "max_wait_time": 0,
        }
    
    async def initialize(self):
        """Initialize the connection pool with a set of connections"""
        if self.initialized:
            return
        
        async with self.pool_lock:
            if self.initialized:  # Double-check to avoid race conditions
                return
                
            logger.info(f"Initializing database pool with {self.max_connections} connections to {self.database_path}")
            for _ in range(self.max_connections):
                connection = await aiosqlite.connect(self.database_path)
                # Enable foreign keys
                await connection.execute("PRAGMA foreign_keys = ON")
                # Set journal mode to WAL for better concurrency
                await connection.execute("PRAGMA journal_mode = WAL")
                # Set busy timeout
                await connection.execute(f"PRAGMA busy_timeout = {int(self.timeout * 1000)}")
                await connection.commit()
                
                self.connections.append(connection)
                self.available.append(True)
                self.connection_locks.append(asyncio.Lock())
                self.stats["connections_created"] += 1
            
            self.initialized = True
            logger.info(f"Database pool initialized with {len(self.connections)} connections")
    
    async def acquire(self) -> tuple[int, aiosqlite.Connection]:
        """Acquire an available connection from the pool"""
        if not self.initialized:
            await self.initialize()
        
        start_time = time.time()
        while True:
            # First try to get an available connection without waiting
            async with self.pool_lock:
                for i, available in enumerate(self.available):
                    if available:
                        self.available[i] = False
                        self.stats["connections_used"] += 1
                        wait_time = time.time() - start_time
                        self.stats["connection_wait_time"] += wait_time
                        if wait_time > self.stats["max_wait_time"]:
                            self.stats["max_wait_time"] = wait_time
                        
                        if wait_time > 1.0:  # Log if wait was longer than 1 second
                            logger.warning(f"Connection {i} acquired after waiting {wait_time:.2f}s")
                        return i, self.connections[i]
            
            # If all connections are busy, wait a bit and try again
            wait_time = time.time() - start_time
            if wait_time > self.timeout:
                raise TimeoutError(f"Timeout waiting for database connection ({wait_time:.2f}s)")
            
            if wait_time > 5.0:  # Log warning if waiting more than 5 seconds
                logger.warning(f"Waiting for database connection for {wait_time:.2f}s")
                
            await asyncio.sleep(0.1)  # Small sleep to avoid CPU spinning
    
    async def release(self, index: int):
        """Release a connection back to the pool"""
        async with self.pool_lock:
            if 0 <= index < len(self.available):
                self.available[index] = True
                logger.debug(f"Released connection {index} back to the pool")
            else:
                logger.error(f"Attempted to release invalid connection index: {index}")
    
    @contextlib.asynccontextmanager
    async def connection(self):
        """Context manager for acquiring and releasing a connection"""
        index = -1
        try:
            index, connection = await self.acquire()
            yield connection
        finally:
            if index >= 0:
                await self.release(index)
    
    async def execute(self, sql: str, parameters: tuple = (), commit: bool = True) -> Optional[Any]:
        """Execute a SQL query and optionally commit the changes"""
        async with self.connection() as connection:
            try:
                cursor = await connection.execute(sql, parameters)
                if commit:
                    await connection.commit()
                return cursor
            except Exception as e:
                logger.error(f"Database error executing {sql[:50]}...: {str(e)}")
                raise
    
    async def execute_many(self, sql: str, parameters_list: list, commit: bool = True) -> Optional[Any]:
        """Execute a SQL query with multiple parameter sets"""
        async with self.connection() as connection:
            try:
                cursor = await connection.executemany(sql, parameters_list)
                if commit:
                    await connection.commit()
                return cursor
            except Exception as e:
                logger.error(f"Database error in execute_many {sql[:50]}...: {str(e)}")
                raise
    
    async def fetchone(self, sql: str, parameters: tuple = ()) -> Optional[tuple]:
        """Execute a query and fetch one result"""
        async with self.connection() as connection:
            try:
                cursor = await connection.execute(sql, parameters)
                return await cursor.fetchone()
            except Exception as e:
                logger.error(f"Database error in fetchone {sql[:50]}...: {str(e)}")
                raise
    
    async def fetchall(self, sql: str, parameters: tuple = ()) -> List[tuple]:
        """Execute a query and fetch all results"""
        async with self.connection() as connection:
            try:
                cursor = await connection.execute(sql, parameters)
                return await cursor.fetchall()
            except Exception as e:
                logger.error(f"Database error in fetchall {sql[:50]}...: {str(e)}")
                raise
    
    async def close(self):
        """Close all connections in the pool"""
        if not self.initialized:
            return
            
        async with self.pool_lock:
            logger.info(f"Closing all {len(self.connections)} database connections")
            for connection in self.connections:
                await connection.close()
            
            self.connections = []
            self.available = []
            self.connection_locks = []
            self.initialized = False
            logger.info("All database connections closed")
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the connection pool"""
        async with self.pool_lock:
            stats = {
                **self.stats,
                "active_connections": self.available.count(False),
                "idle_connections": self.available.count(True),
                "total_connections": len(self.connections),
            }
        return stats

# Singleton database pool instance
db_pool = DatabasePool("leveling.db")

# Helper function to get the connection pool
async def get_db_pool() -> DatabasePool:
    """Get the database connection pool, initializing it if necessary"""
    if not db_pool.initialized:
        await db_pool.initialize()
    return db_pool