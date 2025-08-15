"""
Tests for nl2audio Gmail OAuth module with mocked API responses.
"""
import pytest
from pathlib import Path
import json
import base64
from unittest.mock import Mock, patch

from nl2audio.gmail_oauth import (
    get_label_id, list_messages, extract_message_subject,
    extract_message_content, build_gmail_service
)
from nl2audio.ingest_email import fetch_gmail_oauth, EmailResult


class TestGmailOAuthStub:
    """Test Gmail OAuth functionality with mocked responses."""
    
    def test_get_label_id_success(self, gmail_message):
        """Test successful label ID retrieval."""
        mock_service = Mock()
        mock_service.users.return_value.labels.return_value.list.return_value.execute.return_value = {
            "labels": [
                {"id": "Label_1", "name": "Newsletters"},
                {"id": "Label_2", "name": "INBOX"},
                {"id": "Label_3", "name": "CATEGORY_PERSONAL"}
            ]
        }
        
        label_id = get_label_id(mock_service, "Newsletters")
        assert label_id == "Label_1"
    
    def test_get_label_id_not_found(self, gmail_message):
        """Test label ID retrieval when label doesn't exist."""
        mock_service = Mock()
        mock_service.users.return_value.labels.return_value.list.return_value.execute.return_value = {
            "labels": [
                {"id": "Label_1", "name": "INBOX"},
                {"id": "Label_2", "name": "CATEGORY_PERSONAL"}
            ]
        }
        
        label_id = get_label_id(mock_service, "Newsletters")
        assert label_id is None
    
    def test_list_messages_success(self, gmail_message):
        """Test successful message listing."""
        mock_service = Mock()
        mock_service.users.return_value.messages.return_value.list.return_value.execute.return_value = {
            "messages": [
                {"id": "msg1", "threadId": "thread1"},
                {"id": "msg2", "threadId": "thread2"},
                {"id": "msg3", "threadId": "thread3"}
            ]
        }
        
        # Mock the get method for individual message retrieval
        def mock_get(userId, id):
            mock_get_obj = Mock()
            mock_get_obj.execute.return_value = gmail_message
            return mock_get_obj
        
        mock_service.users.return_value.messages.return_value.get = mock_get
        
        messages = list_messages(mock_service, "Label_1", max_results=3)
        
        assert len(messages) == 3
        assert all("id" in msg for msg in messages)
        assert all("threadId" in msg for msg in messages)
    
    def test_list_messages_empty(self, gmail_message):
        """Test message listing when no messages exist."""
        mock_service = Mock()
        mock_service.users.return_value.messages.return_value.list.return_value.execute.return_value = {
            "messages": []
        }
        
        messages = list_messages(mock_service, "Label_1", max_results=5)
        assert len(messages) == 0
    
    def test_extract_message_subject(self, gmail_message):
        """Test subject extraction from Gmail message."""
        subject = extract_message_subject(gmail_message)
        assert subject == "Weekly Tech Newsletter - Issue #42"
    
    def test_extract_message_subject_missing(self, gmail_message):
        """Test subject extraction when subject is missing."""
        # Remove subject from message
        message_without_subject = gmail_message.copy()
        message_without_subject["payload"]["headers"] = [
            h for h in gmail_message["payload"]["headers"] 
            if h["name"] != "Subject"
        ]
        
        subject = extract_message_subject(message_without_subject)
        assert subject == "No Subject"
    
    def test_extract_message_content_html_preferred(self, gmail_message):
        """Test that HTML content is preferred over plain text."""
        html_content, text_content = extract_message_content(gmail_message)
        
        # Should prefer HTML content
        assert html_content is not None
        assert text_content is not None
        assert len(html_content) > len(text_content)
        
        # HTML content should contain HTML tags
        assert "<html>" in html_content
        assert "<title>" in html_content
        assert "<h1>" in html_content
    
    def test_extract_message_content_plain_text_only(self, gmail_message):
        """Test content extraction when only plain text is available."""
        # Create message with only plain text
        text_only_message = gmail_message.copy()
        text_only_message["payload"]["parts"] = [
            gmail_message["payload"]["parts"][0]  # Only plain text part
        ]
        
        html_content, text_content = extract_message_content(text_only_message)
        
        assert html_content is None
        assert text_content is not None
        assert "Weekly Tech Newsletter" in text_content
    
    def test_extract_message_content_no_content(self, gmail_message):
        """Test content extraction when no content is available."""
        # Create message with no content parts
        no_content_message = gmail_message.copy()
        no_content_message["payload"]["parts"] = []
        
        html_content, text_content = extract_message_content(no_content_message)
        
        assert html_content is None
        assert text_content is None


class TestGmailOAuthIntegration:
    """Test Gmail OAuth integration with mocked dependencies."""
    
    @patch('nl2audio.ingest_email.get_stored_credentials')
    @patch('nl2audio.ingest_email.build_gmail_service')
    @patch('nl2audio.ingest_email.get_label_id')
    @patch('nl2audio.ingest_email.list_messages')
    @patch('nl2audio.ingest_email.extract_message_subject')
    @patch('nl2audio.ingest_email.extract_message_content')
    def test_fetch_gmail_oauth_success(
        self, mock_extract_content, mock_extract_subject, 
        mock_list_messages, mock_get_label_id, mock_build_service, 
        mock_get_credentials, sample_config, gmail_message
    ):
        """Test successful Gmail OAuth email fetching."""
        # Setup mocks
        mock_creds = Mock()
        mock_get_credentials.return_value = mock_creds
        
        mock_service = Mock()
        mock_build_service.return_value = mock_service
        
        mock_get_label_id.return_value = "Label_1"
        
        mock_list_messages.return_value = [gmail_message]
        
        mock_extract_subject.return_value = "Test Subject"
        mock_extract_content.return_value = ("<html>Test HTML</html>", "Test Text")
        
        # Mock the Document class for title extraction
        with patch('nl2audio.ingest_email.Document') as mock_document:
            mock_doc_instance = Mock()
            mock_doc_instance.short_title.return_value = "Extracted Title"
            mock_document.return_value = mock_doc_instance
            
            # Call the function
            results = fetch_gmail_oauth(sample_config.gmail)
        
        # Verify results
        assert len(results) == 1
        assert isinstance(results[0], EmailResult)
        assert results[0].title == "Extracted Title"
        assert results[0].text == "Test Text"  # Should use HTML content converted to text
        assert results[0].source.startswith("email:")
    
    @patch('nl2audio.ingest_email.get_stored_credentials')
    def test_fetch_gmail_oauth_no_credentials(self, mock_get_credentials, sample_config):
        """Test Gmail OAuth when no credentials are available."""
        mock_get_credentials.return_value = None
        
        with pytest.raises(Exception) as exc_info:
            fetch_gmail_oauth(sample_config.gmail)
        
        assert "No valid OAuth credentials found" in str(exc_info.value)
        assert "run 'nl2audio connect-gmail'" in str(exc_info.value)
    
    @patch('nl2audio.ingest_email.get_stored_credentials')
    @patch('nl2audio.ingest_email.build_gmail_service')
    @patch('nl2audio.ingest_email.get_label_id')
    def test_fetch_gmail_oauth_label_not_found(
        self, mock_get_label_id, mock_build_service, 
        mock_get_credentials, sample_config
    ):
        """Test Gmail OAuth when label is not found."""
        # Setup mocks
        mock_creds = Mock()
        mock_get_credentials.return_value = mock_creds
        
        mock_service = Mock()
        mock_build_service.return_value = mock_service
        
        mock_get_label_id.return_value = None
        
        # Mock the labels list method
        mock_service.users.return_value.labels.return_value.list.return_value.execute.return_value = {
            "labels": [
                {"id": "Label_1", "name": "INBOX"},
                {"id": "Label_2", "name": "CATEGORY_PERSONAL"}
            ]
        }
        
        # Call the function
        results = fetch_gmail_oauth(sample_config.gmail)
        
        # Should return empty results when label not found
        assert len(results) == 0


class TestGmailMessageProcessing:
    """Test Gmail message processing utilities."""
    
    def test_message_content_decoding(self, gmail_message):
        """Test that base64 encoded content is properly decoded."""
        # The fixture contains base64 encoded content
        html_part = gmail_message["payload"]["parts"][1]  # HTML part
        encoded_content = html_part["body"]["data"]
        
        # Decode the content
        decoded_content = base64.urlsafe_b64decode(encoded_content + "==").decode('utf-8')
        
        assert "Weekly Tech Newsletter" in decoded_content
        assert "<html>" in decoded_content
        assert "<title>" in decoded_content
    
    def test_message_structure_validation(self, gmail_message):
        """Test that Gmail message structure is valid."""
        # Check required fields
        assert "id" in gmail_message
        assert "threadId" in gmail_message
        assert "payload" in gmail_message
        
        # Check payload structure
        payload = gmail_message["payload"]
        assert "mimeType" in payload
        assert "parts" in payload
        
        # Check parts structure
        parts = payload["parts"]
        assert len(parts) > 0
        
        for part in parts:
            assert "mimeType" in part
            assert "body" in part
            assert "data" in part["body"]
    
    def test_message_label_handling(self, gmail_message):
        """Test that message labels are properly handled."""
        label_ids = gmail_message["labelIds"]
        
        assert "Newsletters" in label_ids
        assert "INBOX" in label_ids
        assert "CATEGORY_PERSONAL" in label_ids
        
        # Should be able to check if message has specific label
        assert "Newsletters" in label_ids 