# Deal Submission Processor

An automated investment deal processing system that handles document submissions, generates critical analysis reports, creates due diligence questionnaires, and manages client communications. Built to streamline the deal evaluation workflow from initial submission to client engagement.

## What It Does

Takes deal submissions from web forms, analyzes the business documents using AI, creates structured due diligence reports, generates investor questions, and automatically manages the entire client communication flow. Handles duplicate detection and organizes everything in Google Drive with proper folder structures.

## Core Features

- **Document Processing**: Uploads and analyzes investment documents
- **AI-Powered Analysis**: Uses Anthropic's Claude to generate critical underwriting reports
- **Due Diligence Automation**: Creates structured investor question sets (KIQs)
- **Duplicate Detection**: Prevents multiple submissions of the same project
- **Client Communication**: Automated email responses with analysis attachments
- **Project Organization**: Creates organized folder structures in Google Drive
- **Internal Notifications**: Alerts the team about new submissions

## System Architecture

The processor handles the complete workflow:

1. **Submission Processing**: Receives deal data from web forms
2. **Duplicate Check**: Searches existing projects to prevent duplicates
3. **Folder Creation**: Sets up organized Google Drive structure
4. **Document Analysis**: Extracts text and generates AI analysis
5. **Report Generation**: Creates underwriting reports and KIQ documents
6. **Client Communication**: Sends personalized emails with attachments
7. **Team Notification**: Internal alerts with project links

## Setup Instructions

### 1. Install Dependencies

```bash
pip install requests google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client
```

### 2. API Setup

**Anthropic Claude API:**
1. Get API key from [Anthropic Console](https://console.anthropic.com/)
2. Note: This uses Claude 3.5 Sonnet for analysis generation

**Google Workspace APIs:**
1. Enable Drive API, Docs API, and Gmail API in Google Cloud Console
2. Create OAuth 2.0 credentials for desktop application
3. Download credentials as `credentials.json`

### 3. Google Drive Setup

Create a base folder in Google Drive for all deal submissions. Get the folder ID from the URL:
`https://drive.google.com/drive/folders/FOLDER_ID_HERE`

### 4. Configuration

Create your config file:
```bash
python deal_processor.py --setup
```

Edit `config.json` with your business details:
```json
{
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
```

Or use environment variables:
```bash
export ANTHROPIC_API_KEY="your_key"
export BASE_FOLDER_ID="your_folder_id"
export GOOGLE_CREDENTIALS_PATH="credentials.json"
```

## Usage

### Test the Processor
```bash
python deal_processor.py --test
```

### Process Individual Submission
```python
from deal_processor import DealProcessor, DealSubmission

processor = DealProcessor()

submission = DealSubmission(
    email="client@example.com",
    first_name="John",
    project_name="Tech Startup Series A",
    document_file="business_plan.pdf"
)

result = processor.process_submission(submission, "path/to/document.pdf")
```

### Webhook Integration
```python
# For JotForm or other webhook integrations
result = processor.process_jotform_webhook(webhook_data)
```

## Generated Analysis Structure

### Underwriting Report Format
```
1. LACK OF DURABLE COMPETITIVE ADVANTAGES
   - Technological Differentiation
   - Market Position
   - Economic Moat Factors
   - Revenue Security
   - Regulatory & Environmental

2. INVESTOR RED FLAGS
   - Investment Structure
   - Management & Execution
   - Financial Considerations
   - Market & Competition
   - Due Diligence Priorities

CONCLUSION
[Critical assessment and recommendations]
```

### KIQ (Key Investor Questions) Structure
```
1. What are they offering as compensation for the contribution of our efforts, networks and capital introduction sources?
A:

2. Does the company have any open litigation, or threats of litigation for any unresolved open matters as disputes with counter parts on agreements?
A:

[13 additional targeted questions based on the analysis]
```

## Project Folder Structure

Each submission creates this Google Drive structure:
```
Email - Project Name/
├── PRE-UNDERWRITE/
│   ├── Original Document
│   └── QS Underwrite Analysis
└── KIQ SUBMISSIONS/
    └── KIQ_1 Questions
```

## Key Features Explained

### Duplicate Detection
Uses email + project name matching to prevent multiple submissions of the same deal. Sends polite notification if duplicate detected.

### Text Extraction
Automatically extracts text from uploaded PDFs and Word documents using Google Drive's export functionality.

### AI Analysis Generation
Uses Anthropic's Claude 3.5 Sonnet to generate:
- Critical investment analysis focusing on weaknesses
- Structured investor questions based on identified issues
- Professional formatting for business use

### Email Automation
Sends two types of emails:
- **Client emails**: Personalized with analysis attachments
- **Internal notifications**: Alerts team with project links

## Error Handling

- Document processing failures fall back to manual review prompts
- API failures are logged with retry mechanisms
- Authentication issues provide clear setup guidance
- Missing files trigger appropriate error messages

## Security Considerations

- All API keys stored in environment variables or config files
- OAuth 2.0 for Google services with proper scopes
- Documents stored in private Google Drive folders
- Email communications from verified business address

## Integration Options

### Web Form Integration
```python
# Flask webhook endpoint example
@app.route('/webhook', methods=['POST'])
def handle_submission():
    data = request.json
    result = processor.process_jotform_webhook(data)
    return {'status': 'processed', 'duplicate': result.duplicate_detected}
```

### Manual Processing
```python
# Direct file processing
processor = DealProcessor()
submission = DealSubmission(...)
result = processor.process_submission(submission, "document.pdf")
```

## Performance Notes

- Document processing: 30-60 seconds depending on size
- AI analysis generation: 10-30 seconds per report
- Google Drive operations: 5-15 seconds per document
- Email delivery: 2-5 seconds

## Monitoring and Logging

All operations logged to:
- Console output for real-time monitoring
- `deal_processor.log` file for historical tracking
- Includes timestamps, operation types, and error details

## Common Issues and Solutions

**"Missing required configuration"**
- Verify all API keys are set correctly
- Check config.json or environment variables

**"Authentication failed"**
- Re-run Google OAuth flow by deleting token.json
- Verify credentials.json is valid

**"Document text extraction failed"**
- Ensure document is readable PDF or Word format
- Check Google Drive API permissions

**"Duplicate project detected"**
- This is normal behavior to prevent double submissions
- Contact support if legitimate resubmission needed

## Customization Options

### Analysis Prompts
Modify the AI prompts in `generate_underwrite_analysis()` and `generate_kiq_questions()` to adjust analysis focus or formatting.

### Email Templates
Update email templates in the `send_client_email()` and related methods.

### Folder Structure
Adjust the `create_project_structure()` method to change folder organization.

### Question Sets
Modify the KIQ generation prompt to change question categories or mandatory questions.

## Deployment Options

### Local Development
Run directly with Python for testing and small-scale processing.

### Cloud Deployment
Deploy to cloud platforms with webhook endpoints for automated processing.

### Docker Container
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "deal_processor.py"]
```