"""
Database connection monitoring middleware for Heroku deployment
"""
import logging
import time
from django.db import connection
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger('mcp.db_monitoring')


class DatabaseConnectionMonitoringMiddleware(MiddlewareMixin):
    """
    Middleware to monitor database connections and log warnings
    when connection limits are approached.
    """
    
    def process_request(self, request):
        """Log database connection status at request start"""
        if connection.connection:
            try:
                with connection.cursor() as cursor:
                    # Check current connection count (PostgreSQL specific)
                    cursor.execute("""
                        SELECT count(*) as connection_count 
                        FROM pg_stat_activity 
                        WHERE state = 'active'
                    """)
                    result = cursor.fetchone()
                    if result:
                        connection_count = result[0]
                        if connection_count > 5:  # Warning threshold
                            logger.warning(
                                f"High database connection count: {connection_count} "
                                f"for {request.path}"
                            )
            except Exception as e:
                logger.debug(f"Could not check connection count: {e}")
        
        request._db_start_time = time.time()
        return None
    
    def process_response(self, request, response):
        """Log database connection status at request end"""
        if hasattr(request, '_db_start_time'):
            db_time = time.time() - request._db_start_time
            
            # Log slow database operations
            if db_time > 2.0:  # 2 second threshold
                logger.warning(
                    f"Slow database operation: {db_time:.2f}s for {request.path}"
                )
            
            # Log connection cleanup
            try:
                if connection.connection and connection.connection.closed == 0:
                    logger.debug(f"Database connection active for {request.path}")
            except Exception as e:
                logger.debug(f"Connection status check failed: {e}")
        
        return response
    
    def process_exception(self, request, exception):
        """Handle database connection errors"""
        if 'connection' in str(exception).lower():
            logger.error(
                f"Database connection error for {request.path}: {exception}"
            )
        
        # Ensure connection is closed on exception
        try:
            connection.close()
        except Exception as e:
            logger.debug(f"Error closing connection: {e}")
        
        return None
