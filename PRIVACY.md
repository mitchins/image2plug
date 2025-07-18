# Privacy and Security Features

## User Privacy

The image2plug web application implements session-based job isolation to ensure user privacy:

### Session Management
- **Secure Sessions**: Each user gets a unique, cryptographically secure session ID
- **24-Hour Expiry**: Sessions automatically expire after 24 hours of inactivity
- **HttpOnly Cookies**: Session cookies are marked as HttpOnly for security
- **Automatic Cleanup**: Expired sessions are automatically removed from memory

### Job Isolation
- **Private Job Lists**: Users can only see and access their own jobs
- **Secure Job Access**: Job details are only available to the job owner
- **UUID-Based URLs**: Job result URLs use unguessable UUIDs for access control
- **Session Validation**: All job operations require valid session ownership

### What Users See
- **Own Jobs Only**: Job queue shows only jobs submitted by the current user
- **Personal Stats**: Statistics reflect only the user's own job counts
- **Queue Position**: If user has pending jobs, shows their position in the global queue
- **Average Processing Time**: Shows system-wide average for estimation purposes

## Security Features

### Rate Limiting
- **Job Submissions**: Maximum 5 job submissions per minute per IP
- **API Calls**: Maximum 60 API calls per minute per IP
- **IP-Based Tracking**: Uses client IP for rate limiting (handles proxies)

### Input Validation
- **File Type Validation**: Only accepts image files
- **File Size Limits**: Maximum 50MB file uploads
- **Image Verification**: Validates uploaded files are actual images using PIL
- **Path Traversal Protection**: Prevents malicious filenames
- **UUID Format Validation**: Ensures job IDs match expected format

### Infrastructure Security
- **CORS Configuration**: Configurable allowed origins
- **Trusted Host Middleware**: Prevents host header attacks
- **Secure Cookie Settings**: Prepared for HTTPS deployment
- **Container Isolation**: Runs in isolated Docker container

## Data Protection

### Temporary Storage
- **Upload Directory**: Uploaded images stored temporarily
- **Result Directories**: Named with job UUIDs for access control
- **Session Memory**: Session data stored in server memory (not persistent)
- **Database Isolation**: SQLite database with job-to-session mapping

### No Cross-User Data Exposure
- **API Endpoints**: All job-related endpoints validate session ownership
- **Error Messages**: Generic "Job not found" for unauthorized access attempts
- **File Serving**: Direct file access only via correct UUID paths
- **No Enumeration**: Impossible to guess or enumerate other users' jobs

## Portfolio Security Highlights

This implementation demonstrates:

1. **Session-Based Security**: Proper web session management
2. **Input Sanitization**: Comprehensive file upload validation
3. **Rate Limiting**: API protection against abuse
4. **Access Control**: Job-level authorization and ownership
5. **Secure Design**: Privacy-by-design architecture
6. **Production-Ready**: Security measures suitable for public deployment

These features make the application suitable for a public demo while protecting user privacy and system security.