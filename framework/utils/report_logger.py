# -*- coding: utf-8 -*-
"""
@Time: 2025/9/1 16:35
@Author: Kilo Code
@File: report_logger.py
@Description: This module provides a logging utility to generate detailed HTML reports for test automation steps.
"""
import base64
import time
from dataclasses import dataclass, field
from datetime import datetime
from io import BytesIO
from typing import List, Optional

from PIL import Image
from playwright.sync_api import Page, Error


@dataclass
class LogStep:
    """
    Represents a single step in a test case, capturing detailed information for reporting.
    """
    order: int
    keyword: str
    description: str
    status: str = 'PASS'
    duration: float = 0.0
    before_screenshot: Optional[str] = None
    after_screenshot: Optional[str] = None
    details: dict = field(default_factory=dict)
    error_message: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    page_url: str = ''


class ReportLogger:
    """
    Manages the logging of test steps and generates an HTML report.
    """

    def __init__(self, page: Page):
        """
        Initializes the logger with a Playwright Page object.

        :param page: The Playwright page to interact with.
        """
        self.page = page
        self.steps: List[LogStep] = []
        self._current_step: Optional[LogStep] = None
        self._step_start_time: Optional[float] = None

    def take_screenshot(self, quality=50) -> Optional[str]:
        """
        Takes a screenshot, compresses it, and returns it as a Base64 encoded string.

        :param quality: The quality of the compressed image (1-100).
        :return: Base64 encoded string of the compressed screenshot, or None on failure.
        """
        try:
            screenshot_bytes = self.page.screenshot(full_page=True)
            img = Image.open(BytesIO(screenshot_bytes))
            
            # Convert to RGB if it's RGBA to avoid issues with saving as JPEG
            if img.mode == 'RGBA':
                img = img.convert('RGB')

            buffered = BytesIO()
            img.save(buffered, format="JPEG", quality=quality, optimize=True)
            return base64.b64encode(buffered.getvalue()).decode('utf-8')
        except Error as e:
            # Handle cases where the page or context might be closed
            print(f"Failed to take screenshot: {e}")
            return None
        except Exception as e:
            # Handle other potential exceptions (e.g., from Pillow)
            print(f"An unexpected error occurred during screenshot: {e}")
            return None

    def start_step(self, keyword: str, description: str, details: Optional[dict] = None):
        """
        Starts a new test step.

        :param keyword: The keyword or action being performed (e.g., 'click', 'fill').
        :param description: A human-readable description of the step.
        :param details: A dictionary with extra data like locators, values, etc.
        """
        if self._current_step:
            # Auto-close the previous step if a new one starts
            self.end_step('PASS')

        self._step_start_time = time.time()
        self._current_step = LogStep(
            order=len(self.steps) + 1,
            keyword=keyword,
            description=description,
            details=details or {},
            before_screenshot=self.take_screenshot(),
            page_url=self.page.url
        )

    def end_step(self, status: str, error: Optional[str] = None):
        """
        Ends the current test step.

        :param status: The status of the step ('PASS' or 'FAIL').
        :param error: The error message if the step failed.
        """
        if not self._current_step or not self._step_start_time:
            return

        self._current_step.duration = round((time.time() - self._step_start_time) * 1000)  # in ms
        self._current_step.status = status
        self._current_step.after_screenshot = self.take_screenshot()

        if status == 'FAIL':
            self._current_step.error_message = error
            self.add_failure_context()

        self.steps.append(self._current_step)
        self._current_step = None
        self._step_start_time = None

    def add_failure_context(self):
        """
        Gathers additional context when a step fails, such as the current URL.
        """
        if self._current_step:
            self._current_step.page_url = self.page.url
            # In the future, we could add more context here, like console logs or network requests.

    def to_html(self) -> str:
        """
        Converts the recorded steps into a self-contained HTML report.
        """
        if not self.steps:
            return "<p>No steps were recorded.</p>"

        # Complete HTML structure with CSS and JavaScript
        html = """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <title>Test Case Report</title>
            <style>
                body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; margin: 20px; background-color: #f8f9fa; color: #333; }
                h2 { color: #007bff; border-bottom: 2px solid #007bff; padding-bottom: 10px; }
                table { width: 100%; border-collapse: collapse; margin-top: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
                th, td { border: 1px solid #dee2e6; padding: 12px; text-align: left; vertical-align: top; }
                th { background-color: #e9ecef; color: #495057; }
                tr.status-FAIL { background-color: #f8d7da; color: #721c24; }
                tr.status-PASS { background-color: #d4edda; color: #155724; }
                .status-FAIL .badge-status { background-color: #dc3545; }
                .status-PASS .badge-status { background-color: #28a745; }
                .badge-status { color: white; padding: 4px 8px; border-radius: 4px; font-weight: bold; }
                .screenshot { max-width: 100%; height: auto; display: none; margin-top: 10px; border: 1px solid #ccc; cursor: pointer; }
                .screenshot-container { margin-top: 10px; }
                .screenshot-toggle { cursor: pointer; color: #007bff; text-decoration: none; font-size: 14px; }
                .screenshot-toggle:hover { text-decoration: underline; }
                .details { white-space: pre-wrap; word-wrap: break-word; font-family: "Courier New", Courier, monospace; background-color: #e9ecef; padding: 8px; border-radius: 4px; margin-top: 5px; }
                .error { color: #721c24; white-space: pre-wrap; word-wrap: break-word; font-family: "Courier New", Courier, monospace; }
            </style>
        </head>
        <body>
            <h2>Test Execution Report</h2>
            <table>
                <thead>
                    <tr>
                        <th>#</th>
                        <th>Timestamp</th>
                        <th>Keyword</th>
                        <th>Description</th>
                        <th>Duration (ms)</th>
                        <th>Status</th>
                        <th>Screenshots & Details</th>
                    </tr>
                </thead>
                <tbody>
        """

        for step in self.steps:
            status_class = f"status-{step.status}"
            html += f'<tr class="{status_class}">'
            html += f'<td>{step.order}</td>'
            html += f'<td>{step.timestamp}</td>'
            html += f'<td>{step.keyword}</td>'
            html += f'<td>{step.description}</td>'
            html += f'<td>{step.duration}</td>'
            html += f'<td><span class="badge-status">{step.status}</span></td>'
            html += '<td>'

            if step.before_screenshot:
                html += f'''
                <div class="screenshot-container">
                    <a href="javascript:void(0);" class="screenshot-toggle" onclick="toggleScreenshot('ss_before_{step.order}')">Show/Hide Before</a>
                    <img id="ss_before_{step.order}" class="screenshot" src="data:image/jpeg;base64,{step.before_screenshot}" onclick="this.style.display='none'">
                </div>
                '''
            if step.after_screenshot:
                html += f'''
                <div class="screenshot-container">
                    <a href="javascript:void(0);" class="screenshot-toggle" onclick="toggleScreenshot('ss_after_{step.order}')">Show/Hide After</a>
                    <img id="ss_after_{step.order}" class="screenshot" src="data:image/jpeg;base64,{step.after_screenshot}" onclick="this.style.display='none'">
                </div>
                '''

            if step.details:
                details_str = '<div class="details">'
                for key, value in step.details.items():
                    details_str += f'<strong>{key}:</strong> {value}<br>'
                details_str += '</div>'
                html += details_str

            if step.error_message:
                html += f'<div class="error"><strong>Error:</strong> {step.error_message}</div>'
            
            if step.page_url:
                html += f'<div class="details"><strong>Page URL:</strong> <a href="{step.page_url}" target="_blank">{step.page_url}</a></div>'

            html += '</td></tr>'

        html += """
                </tbody>
            </table>
            <script>
                function toggleScreenshot(id) {
                    var img = document.getElementById(id);
                    if (img.style.display === 'none') {
                        img.style.display = 'block';
                    } else {
                        img.style.display = 'none';
                    }
                }
            </script>
        </body>
        </html>
        """
        return html

    def clear(self):
        """
        Clears all recorded steps, preparing the logger for a new test case.
        """
        self.steps.clear()
        self._current_step = None
        self._step_start_time = None
