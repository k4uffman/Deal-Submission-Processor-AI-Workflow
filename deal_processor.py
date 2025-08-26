#!/usr/bin/env python3
"""
Deal Submission Processor

Handles investment deal submissions with automated underwriting analysis,
due diligence question generation, and client communication management.
Built to streamline the deal evaluation and client onboarding process.
"""

import os
import json
import time
import logging
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path

import requests
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('deal_processor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class DealSubmission:
    """Data structure for deal submission"""
    email: str
    first_name: str
    project_name: str
    document_file: str
    submission_id: str = None
    created_at: str = None

@dataclass
class ProcessingResult:
    """Results from deal processing"""
    project_folder_id: str
    underwrite_doc_id: str
    kiq_doc_id: str
    duplicate_detected: bool = False

class AnthropicAPI:
    """Handle Anthropic Claude API interactions"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.anthropic.com/v1/messages"
        
    def generate_underwrite_analysis(self, document_text: str) -> str:
        """Generate critical underwriting analysis"""
        headers = {
            'x-api-key': self.api_key,
            'anthropic-version': '2023-06-01',
            'content-type': 'application/json'
        }
        
        prompt = f"""As an industry expert conducting initial pre-due diligence screening, provide only a direct structured analysis without any introductory sentences for the following investment opportunity. Begin immediately with the analysis sections using the information from these quotations and your comprehensive market knowledge:

{document_text}

1. LACK OF DURABLE COMPETITIVE ADVANTAGES

Technological Differentiation
- [Point 1]
- [Point 2]
- [Point 3]

Market Position
- [Point 1]
- [Point 2]
- [Point 3]

Economic Moat Factors
- [Point 1]
- [Point 2]
- [Point 3]

Revenue Security
- [Point 1]
- [Point 2]
- [Point 3]

Regulatory & Environmental
- [Point 1]
- [Point 2]
- [Point 3]

2. INVESTOR RED FLAGS

Investment Structure
- [Point 1]
- [Point 2]
- [Point 3]

Management & Execution
- [Point 1]
- [Point 2]
- [Point 3]

Financial Considerations
- [Point 1]
- [Point 2]
- [Point 3]

Market & Competition
- [Point 1]
- [Point 2]
- [Point 3]

Due Diligence Priorities
- [Point 1]
- [Point 2]
- [Point 3]

CONCLUSION

Provide a 2-3 sentence conclusion highlighting primary competitive vulnerabilities, most critical investor concerns, and recommendation on proceeding with full due diligence. Format as a single paragraph without bullet points.

Formatting Rules:
- Use consistent hyphen (-) for all bullet points
- Leave one blank line between major sections
- No asterisks or other bullet point styles
- No indentation for bullet points
- Capitalize all major section headers
- Use one blank line between subsections
- Format conclusion as a single paragraph without bullets"""

        payload = {
            "model": "claude-3-5-sonnet-20241022",
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}]
        }
        
        try:
            response = requests.post(self.base_url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            return result['content'][0]['text']
            
        except Exception as e:
            logger.error(f"Underwrite analysis failed: {e}")
            return "Analysis generation failed - please review manually."
    
    def generate_kiq_questions(self, underwrite_text: str) -> str:
        """Generate Key Investor Questions based on underwriting analysis"""
        headers = {
            'x-api-key': self.api_key,
            'anthropic-version': '2023-06-01',
            'content-type': 'application/json'
        }
        
        prompt = f"""Based on the following pre-due diligence analysis findings:

{underwrite_text}

Generate exactly 15 due diligence questions, including the two mandatory questions below. Each question should be followed by an 'A:' line for responses. Begin with these mandatory questions:

1. What are they offering as compensation for the contribution of our efforts, networks and capital introduction sources?
A:

2. Does the company have any open litigation, or threats of litigation for any unresolved open matters as disputes with counter parts on agreements?
A:

Generate the remaining 13 questions following this distribution:

WEAKNESSES INVESTIGATION (3 questions)
- Questions targeting competitive disadvantages identified in the analysis
- Queries about gaps in market positioning
- Questions about operational vulnerabilities

COMPETITIVE ADVANTAGE VERIFICATION (3 questions)
- Questions challenging claimed market differentiators
- Queries about sustainability of advantages
- Questions about defensive moat strength

FINANCIAL SCRUTINY (3 questions)
- Questions about projection assumptions
- Queries about capital structure decisions
- Questions about revenue model sustainability

RISK MITIGATION (2 questions)
- Questions about identified risk factors
- Questions about risk management strategies

DUE DILIGENCE GAPS (2 questions)
- Questions about missing critical information
- Questions about verification needs

Format all 15 questions as a single numbered list (1-15), each followed by 'A:' on a new line. Begin immediately with questions without any introduction or context statements."""

        payload = {
            "model": "claude-3-5-sonnet-20241022",
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}]
        }
        
        try:
            response = requests.post(self.base_url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            return result['content'][0]['text']
            
        except Exception as e:
            logger.error(f"KIQ generation failed: {e}")
            return "Question generation failed - please create manually."

class GoogleWorkspaceManager:
    """Handle Google Drive and Gmail operations"""
    
    SCOPES = [
        'https://www.googleapis.com/auth/drive',
        'https://www.googleapis.com/auth/documents',
        'https://www.googleapis.com/auth/gmail.send'
    ]
    
    def __init__(self, credentials_path: str, base_folder_id: str, config: Dict):
        self.base_folder_id = base_folder_id
        self.config = config
        self.drive_service, self.docs_service, self.gmail_service = self._authenticate(credentials_path)
        
    def _authenticate(self, credentials_path: str):
        """Authenticate with Google APIs"""
        creds = None
        token_path = 'token.json'
        
        if os.path.exists(token_path):
            creds = Credentials.from_authorized_user_file(token_path, self.SCOPES)
            
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(credentials_path, self.SCOPES)
                creds = flow.run_local_server(port=0)
                
            with open(token_path, 'w') as token:
                token.write(creds.to_json())
                
        drive_service = build('drive', 'v3', credentials=creds)
        docs_service = build('docs', 'v1', credentials=creds)
        gmail_service = build('gmail', 'v1', credentials=creds)
        
        return drive_service, docs_service, gmail_service
    
    def check_duplicate_project(self, email: str, project_name: str) -> bool:
        """Check if project already exists"""
        try:
            # Clean project name for search
            clean_name = self._clean_text_for_search(project_name)
            search_term = f"{email},{clean_name}"
            
            query = f"name contains '{search_term}' and parents in '{self.base_folder_id}'"
            
            results = self.drive_service.files().list(
                q=query,
                fields="files(id, name)"
            ).execute()
            
            return len(results.get('files', [])) > 0
            
        except Exception as e:
            logger.error(f"Duplicate check failed: {e}")
            return False
    
    def _clean_text_for_search(self, text: str) -> str:
        """Clean text for search compatibility"""
        # Split on various separators and rejoin with commas
        words = re.split(r'[\s\-\.\,\;\:\|\/\_]+', text)
        return ','.join(word for word in words if word)
    
    def create_project_structure(self, submission: DealSubmission) -> Tuple[str, str, str]:
        """Create folder structure for new project"""
        try:
            # Create main project folder
            project_folder = self.drive_service.files().create(
                body={
                    'name': f"{submission.email} - {submission.project_name}",
                    'mimeType': 'application/vnd.google-apps.folder',
                    'parents': [self.base_folder_id]
                }
            ).execute()
            
            project_folder_id = project_folder['id']
            
            # Create PRE-UNDERWRITE subfolder
            preunderwrite_folder = self.drive_service.files().create(
                body={
                    'name': 'PRE-UNDERWRITE',
                    'mimeType': 'application/vnd.google-apps.folder',
                    'parents': [project_folder_id]
                }
            ).execute()
            
            # Create KIQ SUBMISSIONS subfolder
            kiq_folder = self.drive_service.files().create(
                body={
                    'name': 'KIQ SUBMISSIONS',
                    'mimeType': 'application/vnd.google-apps.folder',
                    'parents': [project_folder_id]
                }
            ).execute()
            
            logger.info(f"Created project structure for {submission.project_name}")
            
            return project_folder_id, preunderwrite_folder['id'], kiq_folder['id']
            
        except Exception as e:
            logger.error(f"Failed to create project structure: {e}")
            raise
    
    def upload_document(self, file_path: str, folder_id: str, filename: str = None) -> str:
        """Upload document to Google Drive"""
        try:
            if not filename:
                filename = os.path.basename(file_path)
                
            # Determine if we should convert to Google Docs
            _, ext = os.path.splitext(filename)
            convert = ext.lower() in ['.docx', '.doc']
            
            file_metadata = {
                'name': filename,
                'parents': [folder_id]
            }
            
            # Upload file
            with open(file_path, 'rb') as file_content:
                if convert:
                    file_metadata['mimeType'] = 'application/vnd.google-apps.document'
                    media = {'body': file_content, 'mimetype': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'}
                else:
                    media = {'body': file_content}
                    
                result = self.drive_service.files().create(
                    body=file_metadata,
                    media_body=file_content,
                    convert=convert
                ).execute()
                
            return result['id']
            
        except Exception as e:
            logger.error(f"Failed to upload document: {e}")
            raise
    
    def create_document(self, title: str, content: str, folder_id: str) -> str:
        """Create a Google Doc with content"""
        try:
            # Create the document
            doc = self.docs_service.documents().create(
                body={'title': title}
            ).execute()
            
            doc_id = doc['documentId']
            
            # Add content to the document
            requests = [
                {
                    'insertText': {
                        'location': {'index': 1},
                        'text': content
                    }
                }
            ]
            
            self.docs_service.documents().batchUpdate(
                documentId=doc_id,
                body={'requests': requests}
            ).execute()
            
            # Move to folder
            self.drive_service.files().update(
                fileId=doc_id,
                addParents=folder_id,
                removeParents='root'
            ).execute()
            
            return doc_id
            
        except Exception as e:
            logger.error(f"Failed to create document: {e}")
            raise
    
    def extract_document_text(self, file_id: str) -> str:
        """Extract text from uploaded document"""
        try:
            # Get export link for plain text
            file_metadata = self.drive_service.files().get(
                fileId=file_id,
                fields="exportLinks,mimeType"
            ).execute()
            
            # Try to get plain text export
            export_links = file_metadata.get('exportLinks', {})
            text_link = export_links.get('text/plain')
            
            if text_link:
                # Download the text content
                response = requests.get(text_link)
                response.raise_for_status()
                
                # Clean the text
                text = response.text
                # Remove extra whitespace and clean formatting
                cleaned_text = re.sub(r'[\n\r\t\\"]+', ' ', text)
                cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()
                
                return cleaned_text
            else:
                logger.warning("Could not extract text from document")
                return "Document text extraction failed"
                
        except Exception as e:
            logger.error(f"Text extraction failed: {e}")
            return "Text extraction error"
    
    def send_client_email(self, submission: DealSubmission, underwrite_link: str, kiq_link: str):
        """Send email to client with analysis documents"""
        try:
            subject = f"Your {self.config['company_name']} Deal Submission"
            
            body = f"""Hi {submission.first_name},

Thank you for your submission. I'd like to provide you with two important documents which were built by our Project Optimization Modules for your review and consideration:

The first attachment is our "{self.config['company_name']} Underwrite" document, which presents a hyper-critical analysis of your submitted project. We've specifically designed this analysis to mirror the scrutinizing perspective that potential investors would likely take when evaluating your deal. This thorough examination should provide valuable insights into how your project might be perceived by investment stakeholders.

Additionally, you'll find the "KIQ_1" document which contains essential questions for your team to address regarding the deal. 

Once you've completed the KIQ (Key Investor Questions) worksheet, if you're interested in learning more about our services and potentially engaging with our full suite of Project Optimization Modules, we would be happy to schedule a call to discuss next steps.

{self.config['company_name']} Underwrite Analysis: {underwrite_link}

Key Investor Questions (KIQ_1): {kiq_link}

Best regards,

{self.config['signature_name']} | {self.config['signature_title']} | {self.config['company_name']}
{self.config['phone_number']}"""

            # Create email message
            message = {
                'raw': self._create_message_raw(submission.email, subject, body)
            }
            
            self.gmail_service.users().messages().send(
                userId='me',
                body=message
            ).execute()
            
            logger.info(f"Sent client email to {submission.email}")
            
        except Exception as e:
            logger.error(f"Failed to send client email: {e}")
    
    def send_internal_notification(self, submission: DealSubmission, project_link: str, 
                                 underwrite_link: str, kiq_link: str):
        """Send internal notification about new deal"""
        try:
            subject = "NEW DEAL SUBMITTED"
            
            body = f"""New Deal Submission from: {submission.email}

Project Name: {submission.project_name}

Underwriting Report: {underwrite_link}

KIQ's: {kiq_link}

Project Folder: {project_link}"""

            # Send to internal team
            internal_emails = self.config.get('internal_notification_emails', [])
            
            for email in internal_emails:
                message = {
                    'raw': self._create_message_raw(email, subject, body)
                }
                
                self.gmail_service.users().messages().send(
                    userId='me',
                    body=message
                ).execute()
            
            logger.info("Sent internal notifications")
            
        except Exception as e:
            logger.error(f"Failed to send internal notification: {e}")
    
    def send_duplicate_notification(self, submission: DealSubmission):
        """Send notification about duplicate submission"""
        try:
            subject = f"Duplicate Project Submission Detected - {self.config['company_name']}"
            
            body = f"""Dear {submission.first_name},

We've detected that you've already submitted a project with this name. To maintain accurate records in our system, please submit each project only once.

If you believe this is an error or need to submit an updated version, please contact our support team at {self.config['support_url']}.

Best regards,

{self.config['company_name']}"""

            message = {
                'raw': self._create_message_raw(submission.email, subject, body)
            }
            
            self.gmail_service.users().messages().send(
                userId='me',
                body=message
            ).execute()
            
            logger.info(f"Sent duplicate notification to {submission.email}")
            
        except Exception as e:
            logger.error(f"Failed to send duplicate notification: {e}")
    
    def _create_message_raw(self, to_email: str, subject: str, body: str) -> str:
        """Create raw email message"""
        import base64
        from email.mime.text import MIMEText
        
        message = MIMEText(body)
        message['to'] = to_email
        message['from'] = self.config['from_email']
        message['subject'] = subject
        
        return base64.urlsafe_b64encode(message.as_bytes()).decode()

class DealProcessor:
    """Main deal processing orchestrator"""
    
    def __init__(self, config_path: str = 'config.json'):
        self.config = self._load_config(config_path)
        
        self.anthropic = AnthropicAPI(self.config['anthropic_api_key'])
        self.workspace = GoogleWorkspaceManager(
            self.config['google_credentials_path'],
            self.config['base_folder_id'],
            self.config
        )
        
    def _load_config(self, config_path: str) -> Dict:
        """Load configuration"""
        config = {}
        
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                config = json.load(f)
        
        # Environment variables override config file
        final_config = {
            'anthropic_api_key': os.getenv('ANTHROPIC_API_KEY', config.get('anthropic_api_key')),
            'google_credentials_path': os.getenv('GOOGLE_CREDENTIALS_PATH', config.get('google_credentials_path', 'credentials.json')),
            'base_folder_id': os.getenv('BASE_FOLDER_ID', config.get('base_folder_id')),
            'from_email': os.getenv('FROM_EMAIL', config.get('from_email')),
            'internal_notification_emails': config.get('internal_notification_emails', []),
            'company_name': config.get('company_name', 'Your Company'),
            'signature_name': config.get('signature_name', 'Your Name'),
            'signature_title': config.get('signature_title', 'Your Title'),
            'phone_number': config.get('phone_number', 'Your Phone Number'),
            'support_url': config.get('support_url', 'https://your-website.com/contact')
        }
        
        # Required fields that must be present
        required_fields = ['anthropic_api_key', 'base_folder_id', 'from_email']
        missing = [key for key in required_fields if not final_config.get(key)]
        
        if missing:
            raise ValueError(f"Missing required configuration: {missing}")
            
        return final_config
    
    def process_submission(self, submission: DealSubmission, document_path: str) -> ProcessingResult:
        """Process a complete deal submission"""
        try:
            logger.info(f"Processing submission for {submission.project_name}")
            
            # Check for duplicates
            if self.workspace.check_duplicate_project(submission.email, submission.project_name):
                logger.info(f"Duplicate detected for {submission.project_name}")
                self.workspace.send_duplicate_notification(submission)
                return ProcessingResult("", "", "", duplicate_detected=True)
            
            # Create project structure
            project_folder_id, preunderwrite_folder_id, kiq_folder_id = \
                self.workspace.create_project_structure(submission)
            
            # Upload original document
            uploaded_doc_id = self.workspace.upload_document(
                document_path, 
                preunderwrite_folder_id,
                f"{submission.email} - {submission.project_name} - Original"
            )
            
            # Extract text from document
            logger.info("Extracting document text...")
            document_text = self.workspace.extract_document_text(uploaded_doc_id)
            
            # Generate underwriting analysis
            logger.info("Generating underwriting analysis...")
            underwrite_analysis = self.anthropic.generate_underwrite_analysis(document_text)
            
            # Create underwrite document
            underwrite_title = f"{submission.email} - {submission.project_name} - {self.config['company_name']} Underwrite"
            underwrite_doc_id = self.workspace.create_document(
                underwrite_title,
                underwrite_analysis,
                preunderwrite_folder_id
            )
            
            # Generate KIQ questions
            logger.info("Generating KIQ questions...")
            kiq_questions = self.anthropic.generate_kiq_questions(underwrite_analysis)
            
            # Create KIQ document
            kiq_title = f"{submission.email} - {submission.project_name} - KIQ_1"
            kiq_doc_id = self.workspace.create_document(
                kiq_title,
                kiq_questions,
                kiq_folder_id
            )
            
            # Generate document links
            project_link = f"https://drive.google.com/drive/folders/{project_folder_id}"
            underwrite_link = f"https://docs.google.com/document/d/{underwrite_doc_id}"
            kiq_link = f"https://docs.google.com/document/d/{kiq_doc_id}"
            
            # Send notifications
            self.workspace.send_client_email(submission, underwrite_link, kiq_link)
            self.workspace.send_internal_notification(submission, project_link, underwrite_link, kiq_link)
            
            logger.info(f"Successfully processed submission for {submission.project_name}")
            
            return ProcessingResult(
                project_folder_id=project_folder_id,
                underwrite_doc_id=underwrite_doc_id,
                kiq_doc_id=kiq_doc_id,
                duplicate_detected=False
            )
            
        except Exception as e:
            logger.error(f"Failed to process submission: {e}")
            raise
    
    def process_jotform_webhook(self, webhook_data: Dict) -> ProcessingResult:
        """Process incoming JotForm webhook data"""
        try:
            # Extract submission data from webhook
            answers = webhook_data.get('answers', {})
            
            # Map JotForm fields (adjust field IDs as needed)
            submission = DealSubmission(
                email=answers.get('Email', ''),
                first_name=answers.get('Name - First Name', ''),
                project_name=answers.get('Project Name', ''),
                document_file=answers.get('Please upload your document in PDF or .DOCX Format', ''),
                submission_id=webhook_data.get('submissionID'),
                created_at=webhook_data.get('created_at')
            )
            
            # Download document from JotForm (implement based on JotForm API)
            document_path = self._download_jotform_file(submission.document_file)
            
            # Process the submission
            return self.process_submission(submission, document_path)
            
        except Exception as e:
            logger.error(f"Failed to process JotForm webhook: {e}")
            raise
    
    def _download_jotform_file(self, file_url: str) -> str:
        """Download file from JotForm submission"""
        # This would implement the actual file download from JotForm
        # For now, return a placeholder
        logger.info(f"Would download file from: {file_url}")
        return "/tmp/downloaded_file.pdf"

def create_sample_config():
    """Create a sample configuration file"""
    sample_config = {
        "anthropic_api_key": "your_anthropic_key",
        "google_credentials_path": "credentials.json", 
        "base_folder_id": "your_drive_folder_id",
        "from_email": "your-email@company.com",
        "internal_notification_emails": ["team@company.com", "manager@company.com"],
        "company_name": "Your Company Name",
        "signature_name": "Your Name", 
        "signature_title": "Your Title",
        "phone_number": "Your Phone Number",
        "support_url": "https://your-website.com/contact"
    }
    
    with open('config.json', 'w') as f:
        json.dump(sample_config, f, indent=2)
    
    print("Sample config.json created. Update with your API keys and settings.")

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Deal Submission Processor')
    parser.add_argument('--test', action='store_true', help='Run test processing')
    parser.add_argument('--setup', action='store_true', help='Create sample config')
    parser.add_argument('--config', default='config.json', help='Config file path')
    
    args = parser.parse_args()
    
    if args.setup:
        create_sample_config()
        return
    
    try:
        processor = DealProcessor(args.config)
        
        if args.test:
            # Test with sample data
            test_submission = DealSubmission(
                email="test@example.com",
                first_name="Test",
                project_name="Sample Project",
                document_file="sample.pdf"
            )
            
            # You would need a test document file
            result = processor.process_submission(test_submission, "test_document.pdf")
            print(f"Test processing result: {result}")
        else:
            print("Deal processor ready. Use --test to run a test or integrate with webhook endpoint.")
            
    except Exception as e:
        logger.error(f"Application error: {e}")

if __name__ == '__main__':
    main()