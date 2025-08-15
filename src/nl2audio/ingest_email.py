from dataclasses import dataclass
from imap_tools import MailBox
from .ingest import _html_to_text
from readability import Document
from .gmail_oauth import (
    get_stored_credentials, build_gmail_service, get_label_id,
    list_messages, extract_message_subject, extract_message_content,
    GmailOAuthError
)

@dataclass
class EmailResult:
    title: str
    text: str
    source: str

def fetch_gmail_oauth(cfg):
    """Fetch emails using Gmail OAuth API."""
    results = []
    print(f"🔍 Connecting to Gmail via OAuth for user: {cfg.user}")
    print(f"🏷️  Looking for emails with label: '{cfg.label}'")
    
    try:
        # Get stored credentials
        creds = get_stored_credentials(cfg.user)
        if not creds:
            raise GmailOAuthError(
                f"No valid OAuth credentials found for {cfg.user}\n"
                "Please run 'nl2audio connect-gmail' first to authenticate."
            )
        
        # Build Gmail service
        service = build_gmail_service(creds)
        print("✅ Successfully connected to Gmail via OAuth")
        
        # Get label ID
        label_id = get_label_id(service, cfg.label)
        if not label_id:
            print(f"❌ Label '{cfg.label}' not found")
            # List available labels
            try:
                labels_result = service.users().labels().list(userId='me').execute()
                labels = labels_result.get('labels', [])
                print(f"📁 Available labels: {[label['name'] for label in labels[:10]]}")
                if len(labels) > 10:
                    print(f"   ... and {len(labels) - 10} more")
            except Exception as e:
                print(f"⚠️  Could not list labels: {e}")
            return results
        
        # List messages
        messages = list_messages(service, label_id, max_results=50)
        print(f"📧 Found {len(messages)} messages in label '{cfg.label}'")
        
        if messages:
            print("📋 Processing emails:")
            for i, msg in enumerate(messages):
                subject = extract_message_subject(msg)
                html_content, text_content = extract_message_content(msg)
                
                if not html_content and not text_content:
                    print(f"  {i+1}. ⚠️  Email has no content, skipping: {subject}")
                    continue
                
                # Prefer HTML content
                content = html_content if html_content else text_content
                
                try:
                    title = Document(content).short_title() or subject
                except:
                    title = subject
                
                text = _html_to_text(content)
                results.append(EmailResult(
                    title=title, 
                    text=text, 
                    source=f"email:{msg['id']}"
                ))
                print(f"  {i+1}. ✅ Processed: {title}")
        
        else:
            print("❌ No emails found with this label!")
            
    except GmailOAuthError as e:
        print(f"❌ OAuth error: {e}")
        raise
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        raise
    
    print(f"\n📊 Total emails processed: {len(results)}")
    return results

def fetch_gmail_imap(cfg):
    """Fetch emails using IMAP (fallback method)."""
    results = []
    print(f"🔍 Connecting to Gmail via IMAP for user: {cfg.user}")
    print(f"🏷️  Looking for emails with label: '{cfg.label}'")
    
    with MailBox('imap.gmail.com').login(cfg.user, cfg.app_password) as mailbox:
        print("✅ Successfully connected to Gmail via IMAP")
        
        # First, let's see what labels are available
        try:
            labels = mailbox.folder.list()
            print(f"📁 Available folders/labels: {[f.name for f in labels]}")
        except Exception as e:
            print(f"⚠️  Could not list folders: {e}")
        
        # Process ALL emails in the Newsletters label (including read ones)
        print(f"🔍 Processing ALL emails in label '{cfg.label}'...")
        try:
            all_labeled = list(mailbox.fetch(f'X-GM-LABELS "{cfg.label}"'))
            print(f"📧 Found {len(all_labeled)} total emails with label '{cfg.label}'")
            
            if all_labeled:
                print("📋 Processing emails in this label:")
                for i, msg in enumerate(all_labeled):
                    status = "UNREAD" if "\\Seen" not in msg.flags else "READ"
                    print(f"  {i+1}. [{status}] {msg.subject} (UID: {msg.uid})")
                    
                    html = msg.html or msg.text
                    if not html:
                        print(f"    ⚠️  Email has no HTML/text content, skipping")
                        continue
                    
                    try:
                        title = Document(html).short_title() or msg.subject
                    except:
                        title = msg.subject
                    
                    text = _html_to_text(html)
                    results.append(EmailResult(title=title, text=text, source=f"email:{msg.uid}"))
                    print(f"    ✅ Processed: {title}")
                    
            else:
                print("❌ No emails found with this label!")
                
        except Exception as e:
            print(f"⚠️  Could not process label contents: {e}")
            print("🔄 Falling back to fetching all unread emails...")
            
            # Fallback: search for unread emails
            try:
                unseen_all = list(mailbox.fetch('UNSEEN'))
                print(f"📧 Found {len(unseen_all)} total unread emails")
                
                for msg in unseen_all:
                    html = msg.html or msg.text
                    if not html:
                        continue
                    try:
                        title = Document(html).short_title() or msg.subject
                    except:
                        title = msg.subject
                    text = _html_to_text(html)
                    results.append(EmailResult(title=title, text=text, source=f"email:{msg.uid}"))
                    print(f"✅ Processed unread email: {title}")
                    
            except Exception as e2:
                print(f"❌ Fallback also failed: {e2}")
    
    print(f"\n📊 Total emails processed: {len(results)}")
    return results

def fetch_gmail(cfg):
    """Fetch emails using the configured method (OAuth preferred, IMAP fallback)."""
    if cfg.method == "oauth":
        try:
            return fetch_gmail_oauth(cfg)
        except Exception as e:
            print(f"⚠️  OAuth method failed: {e}")
            print("🔄 Falling back to IMAP method...")
            if cfg.app_password:
                return fetch_gmail_imap(cfg)
            else:
                raise Exception(
                    "OAuth failed and no app password configured for IMAP fallback.\n"
                    "Please either fix OAuth or configure an app password."
                )
    else:
        # Use IMAP method
        if not cfg.app_password:
            raise Exception("App password required for IMAP method")
        return fetch_gmail_imap(cfg)
