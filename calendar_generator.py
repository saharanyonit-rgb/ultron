#!/usr/bin/env python3
"""
Calendar Generator with Important Date Marking

This script generates a calendar for any given month/year and allows
marking important dates with custom labels.
"""

import calendar
import json
import os
from datetime import datetime, date


class CalendarGenerator:
    def __init__(self, important_dates_file="important_dates.json"):
        self.important_dates_file = important_dates_file
        self.important_dates = self._load_important_dates()

    def _load_important_dates(self):
        """Load important dates from JSON file if it exists."""
        if os.path.exists(self.important_dates_file):
            try:
                with open(self.important_dates_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {}
        return {}

    def _save_important_dates(self):
        """Save important dates to JSON file."""
        with open(self.important_dates_file, 'w') as f:
            json.dump(self.important_dates, f, indent=2)

    def add_important_date(self, date_str, label):
        """Add an important date with a label.

        Args:
            date_str: Date in 'YYYY-MM-DD' format
            label: Description of the important event
        """
        try:
            # Validate date format
            parsed_date = datetime.strptime(date_str, "%Y-%m-%d")
            self.important_dates[date_str] = label
            self._save_important_dates()
            print(f"✓ Added important date: {date_str} - {label}")
        except ValueError:
            print("✗ Invalid date format. Please use YYYY-MM-DD format.")

    def remove_important_date(self, date_str):
        """Remove an important date.

        Args:
            date_str: Date in 'YYYY-MM-DD' format
        """
        if date_str in self.important_dates:
            del self.important_dates[date_str]
            self._save_important_dates()
            print(f"✓ Removed important date: {date_str}")
        else:
            print(f"✗ No important date found for {date_str}")

    def list_important_dates(self):
        """List all important dates."""
        if not self.important_dates:
            print("No important dates marked.")
            return

        print("\nImportant Dates:")
        print("-" * 40)
        for date_str in sorted(self.important_dates.keys()):
            print(f"{date_str}: {self.important_dates[date_str]}")

    def generate_calendar(self, year, month):
        """Generate a calendar for the specified month and year.

        Args:
            year: Year as integer
            month: Month as integer (1-12)
        """
        # Create calendar
        cal = calendar.TextCalendar(calendar.SUNDAY)
        month_calendar = cal.monthdays2calendar(year, month)

        # Month and year header
        month_name = calendar.month_name[month]
        print(f"\n{'='*30}")
        print(f"     {month_name} {year}")
        print(f"{'='*30}")
        print("Su Mo Tu We Th Fr Sa")

        # Generate calendar rows
        for week in month_calendar:
            week_str = ""
            for day, weekday in week:
                if day == 0:
                    week_str += "   "
                else:
                    date_str = f"{year}-{month:02d}-{day:02d}"
                    if date_str in self.important_dates:
                        # Mark important dates with *
                        week_str += f"{day:02d}* "
                    else:
                        week_str += f"{day:02d}  "
            print(week_str.rstrip())

        # Print legend
        print("\nLegend:")
        print("* = Important date")

        # Show important dates for this month
        month_important = {
            d: label for d, label in self.important_dates.items()
            if d.startswith(f"{year}-{month:02d}")
        }

        if month_important:
            print("\nImportant dates this month:")
            for date_str in sorted(month_important.keys()):
                print(f"  {date_str}: {month_important[date_str]}")

    def generate_year_calendar(self, year):
        """Generate a calendar for the entire year.

        Args:
            year: Year as integer
        """
        print(f"\n{'#'*50}")
        print(f"# Calendar for {year}")
        print(f"{'#'*50}")

        for month in range(1, 13):
            self.generate_calendar(year, month)

    def get_current_month_calendar(self):
        """Generate calendar for the current month."""
        today = date.today()
        self.generate_calendar(today.year, today.month)


def main():
    cal_gen = CalendarGenerator()

    while True:
        print("\n" + "="*40)
        print("Calendar Generator")
        print("="*40)
        print("1. Generate calendar for a specific month")
        print("2. Generate calendar for a specific year")
        print("3. Show current month calendar")
        print("4. Add important date")
        print("5. Remove important date")
        print("6. List all important dates")
        print("7. Exit")

        choice = input("\nEnter your choice (1-7): ").strip()

        if choice == '1':
            try:
                year = int(input("Enter year (e.g., 2024): "))
                month = int(input("Enter month (1-12): "))
                if 1 <= month <= 12:
                    cal_gen.generate_calendar(year, month)
                else:
                    print("✗ Invalid month. Please enter a number between 1 and 12.")
            except ValueError:
                print("✗ Please enter valid numbers.")

        elif choice == '2':
            try:
                year = int(input("Enter year (e.g., 2024): "))
                cal_gen.generate_year_calendar(year)
            except ValueError:
                print("✗ Please enter a valid year.")

        elif choice == '3':
            cal_gen.get_current_month_calendar()

        elif choice == '4':
            date_str = input("Enter date (YYYY-MM-DD): ").strip()
            label = input("Enter label/description: ").strip()
            if label:
                cal_gen.add_important_date(date_str, label)
            else:
                print("✗ Label cannot be empty.")

        elif choice == '5':
            date_str = input("Enter date to remove (YYYY-MM-DD): ").strip()
            cal_gen.remove_important_date(date_str)

        elif choice == '6':
            cal_gen.list_important_dates()

        elif choice == '7':
            print("Goodbye!")
            break

        else:
            print("✗ Invalid choice. Please enter a number between 1 and 7.")


if __name__ == "__main__":
    main()