import re
from datetime import datetime, timedelta
import pytz
import logging

logger = logging.getLogger(__name__)

class DateTimeExtractor:
    """Extract date and time information from natural language text"""
    
    @staticmethod
    def extract_datetime(text):
        """Extract date and time from text - returns a datetime object or None"""
        now = datetime.now()
        
        # Handle relative time patterns
        patterns = {
            # Today or tonight
            r'today|tonight': lambda m: now.replace(hour=20, minute=0, second=0, microsecond=0) if 'tonight' in m.group(0) else now,
            
            # Tomorrow
            r'tomorrow': lambda m: (now + timedelta(days=1)).replace(hour=12, minute=0, second=0, microsecond=0),
            
            # Next week
            r'next week': lambda m: (now + timedelta(days=7)).replace(hour=12, minute=0, second=0, microsecond=0),
            
            # This/next month
            r'this month': lambda m: now.replace(day=15, hour=12, minute=0, second=0, microsecond=0),
            r'next month': lambda m: (now.replace(day=1) + timedelta(days=32)).replace(day=15, hour=12, minute=0, second=0, microsecond=0),
            
            # Day of week
            r'(this |next )?(monday|tuesday|wednesday|thursday|friday|saturday|sunday)': lambda m: DateTimeExtractor._get_next_weekday(now, m.group(2).lower(), 'next' in m.group(0)),
            
            # In X days/hours/minutes
            r'in (\d+) (day|days|hour|hours|minute|minutes)': lambda m: now + DateTimeExtractor._parse_relative_time(int(m.group(1)), m.group(2)),
            
            # On specific date (MM/DD/YYYY or DD/MM/YYYY)
            r'on (\d{1,2})[/.-](\d{1,2})(?:[/.-](\d{2,4}))?': lambda m: DateTimeExtractor._parse_date_format(m.group(1), m.group(2), m.group(3)),
            
            # At specific time (HH:MM)
            r'at (\d{1,2}):?(\d{2})?\s*(am|pm)?': lambda m: DateTimeExtractor._parse_time_format(now, m.group(1), m.group(2), m.group(3)),
        }
        
        # Try each pattern
        for pattern, handler in patterns.items():
            match = re.search(pattern, text.lower())
            if match:
                try:
                    return handler(match)
                except Exception as e:
                    logger.warning(f"Error parsing date/time with pattern {pattern}: {e}")
        
        return None
    
    @staticmethod
    def _parse_relative_time(amount, unit):
        """Parse relative time expressions like '5 days'"""
        if 'day' in unit:
            return timedelta(days=amount)
        elif 'hour' in unit:
            return timedelta(hours=amount)
        elif 'minute' in unit:
            return timedelta(minutes=amount)
        return timedelta(0)
    
    @staticmethod
    def _get_next_weekday(now, weekday, next_week=False):
        """Get the date of the next occurrence of a weekday"""
        days = {
            'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
            'friday': 4, 'saturday': 5, 'sunday': 6
        }
        
        target_day = days.get(weekday.lower())
        if target_day is None:
            return now
        
        days_ahead = target_day - now.weekday()
        if days_ahead <= 0 or next_week:  # Target day already happened this week
            days_ahead += 7
        
        return (now + timedelta(days=days_ahead)).replace(hour=12, minute=0, second=0, microsecond=0)
    
    @staticmethod
    def _parse_date_format(day, month, year=None):
        """Parse a date in MM/DD/YYYY or DD/MM/YYYY format"""
        now = datetime.now()
        
        # Handle two-digit years
        if year:
            if len(year) == 2:
                year = int(year)
                # Assume 00-49 -> 2000-2049, 50-99 -> 1950-1999
                if year < 50:
                    year += 2000
                else:
                    year += 1900
        else:
            year = now.year
        
        try:
            # Try MM/DD/YYYY (US format)
            return datetime(int(year), int(day), int(month), 12, 0, 0)
        except ValueError:
            try:
                # Try DD/MM/YYYY (European format)
                return datetime(int(year), int(month), int(day), 12, 0, 0)
            except ValueError:
                return now
    
    @staticmethod
    def _parse_time_format(base_date, hour, minute=None, ampm=None):
        """Parse a time in HH:MM AM/PM format"""
        hour = int(hour)
        minute = int(minute) if minute else 0
        
        # Handle AM/PM
        if ampm and ampm.lower() == 'pm' and hour < 12:
            hour += 12
        elif ampm and ampm.lower() == 'am' and hour == 12:
            hour = 0
        
        return base_date.replace(hour=hour, minute=minute, second=0, microsecond=0)