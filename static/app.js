/**
 * image2plug Web Frontend
 * Material UI styled interface for job submission and monitoring
 */

class JobManager {
    constructor() {
        this.selectedFile = null;
        this.pollInterval = null;
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.preventDefaultDragBehavior();
        this.refreshJobs();
        this.startPolling();
    }

    preventDefaultDragBehavior() {
        // Prevent default drag behaviors on the document
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            document.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
            }, false);
        });
    }

    setupEventListeners() {
        // File upload handling
        const uploadArea = document.getElementById('uploadArea');
        const fileInput = document.getElementById('fileInput');
        const jobForm = document.getElementById('jobForm');

        // Click to browse
        uploadArea.addEventListener('click', (e) => {
            e.preventDefault();
            fileInput.click();
        });

        // Drag and drop
        uploadArea.addEventListener('dragenter', (e) => {
            e.preventDefault();
            e.stopPropagation();
            uploadArea.classList.add('dragover');
        });

        uploadArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            e.stopPropagation();
            uploadArea.classList.add('dragover');
        });

        uploadArea.addEventListener('dragleave', (e) => {
            e.preventDefault();
            e.stopPropagation();
            // Only remove dragover if we're actually leaving the upload area
            if (!uploadArea.contains(e.relatedTarget)) {
                uploadArea.classList.remove('dragover');
            }
        });

        uploadArea.addEventListener('drop', (e) => {
            e.preventDefault();
            e.stopPropagation();
            uploadArea.classList.remove('dragover');
            
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                this.handleFileSelect(files[0]);
            }
        });

        // File input change
        fileInput.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                this.handleFileSelect(e.target.files[0]);
            }
        });

        // Form submission
        jobForm.addEventListener('submit', (e) => {
            e.preventDefault();
            this.submitJob();
        });
    }

    handleFileSelect(file) {
        // Validate file type
        if (!file.type.startsWith('image/')) {
            this.showStatus('error', 'Please select an image file.');
            return;
        }

        // Validate file size (50MB)
        const maxSize = 50 * 1024 * 1024;
        if (file.size > maxSize) {
            this.showStatus('error', 'File is too large. Maximum size is 50MB.');
            return;
        }

        this.selectedFile = file;
        
        // Also set the file input value so the form knows a file is selected
        // Create a new FileList and assign it to the input
        const dt = new DataTransfer();
        dt.items.add(file);
        document.getElementById('fileInput').files = dt.files;
        
        // Update upload area
        const uploadArea = document.getElementById('uploadArea');
        const uploadIcon = uploadArea.querySelector('.upload-icon');
        const uploadText = uploadArea.querySelector('p');
        
        uploadIcon.textContent = 'check_circle';
        uploadIcon.style.color = '#4caf50';
        uploadText.innerHTML = `<strong>${file.name}</strong><br><small>${this.formatFileSize(file.size)}</small>`;
        
        this.clearStatus();
    }

    async submitJob() {
        if (!this.selectedFile) {
            this.showStatus('error', 'Please select an image file.');
            return;
        }

        const submitBtn = document.getElementById('submitBtn');
        const originalText = submitBtn.textContent;
        
        try {
            // Disable button and show loading
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<span class="loading"></span> Submitting...';

            // Prepare form data
            const formData = new FormData();
            formData.append('file', this.selectedFile);
            formData.append('proof', document.getElementById('proof').checked);
            formData.append('extrude_height', document.getElementById('extrudeHeight').value);
            formData.append('smooth', document.getElementById('smooth').checked);
            formData.append('measure_error', document.getElementById('measureError').checked);
            formData.append('border_mode', document.getElementById('borderMode').value);

            // Submit job
            const response = await fetch('/api/jobs', {
                method: 'POST',
                body: formData
            });

            const result = await response.json();

            if (!response.ok) {
                throw new Error(result.detail || 'Failed to submit job');
            }

            // Success
            this.showStatus('success', `Job submitted successfully! Job ID: ${result.job_id}`);
            this.resetForm();
            this.refreshJobs();

        } catch (error) {
            console.error('Job submission error:', error);
            this.showStatus('error', `Failed to submit job: ${error.message}`);
        } finally {
            // Re-enable button
            submitBtn.disabled = false;
            submitBtn.textContent = originalText;
        }
    }

    resetForm() {
        // Reset file selection
        this.selectedFile = null;
        document.getElementById('fileInput').value = '';
        
        // Reset upload area
        const uploadArea = document.getElementById('uploadArea');
        const uploadIcon = uploadArea.querySelector('.upload-icon');
        const uploadText = uploadArea.querySelector('p');
        
        uploadIcon.textContent = 'cloud_upload';
        uploadIcon.style.color = '#ccc';
        uploadText.innerHTML = 'Drop an image here or <strong>click to browse</strong>';
        
        // Reset form
        document.getElementById('jobForm').reset();
        document.getElementById('proof').checked = true;
        document.getElementById('extrudeHeight').value = '10.0';
    }

    async refreshJobs() {
        const spinner = document.getElementById('refreshSpinner');
        
        try {
            spinner.style.display = 'inline-block';
            
            // Fetch stats and jobs
            const [statsResponse, jobsResponse] = await Promise.all([
                fetch('/api/stats'),
                fetch('/api/jobs?limit=20')
            ]);

            const stats = await statsResponse.json();
            const jobs = await jobsResponse.json();

            this.updateStats(stats);
            this.updateJobList(jobs);

        } catch (error) {
            console.error('Failed to refresh jobs:', error);
        } finally {
            spinner.style.display = 'none';
        }
    }

    updateStats(stats) {
        const statsGrid = document.getElementById('statsGrid');
        
        let statsHtml = `
            <div class="stat-item">
                <div class="stat-number">${stats.pending}</div>
                <div class="stat-label">Your Pending</div>
            </div>
            <div class="stat-item">
                <div class="stat-number">${stats.running}</div>
                <div class="stat-label">Your Running</div>
            </div>
            <div class="stat-item">
                <div class="stat-number">${stats.completed}</div>
                <div class="stat-label">Your Completed</div>
            </div>
            <div class="stat-item">
                <div class="stat-number">${stats.failed}</div>
                <div class="stat-label">Your Failed</div>
            </div>
        `;
        
        // Add queue position if user has pending jobs
        if (stats.queue_position) {
            statsHtml += `
                <div class="stat-item">
                    <div class="stat-number">${stats.queue_position}</div>
                    <div class="stat-label">Queue Position</div>
                </div>
            `;
        }
        
        // Add average processing time if available
        if (stats.average_processing_time) {
            statsHtml += `
                <div class="stat-item">
                    <div class="stat-number">${stats.average_processing_time.toFixed(1)}s</div>
                    <div class="stat-label">Avg Process Time</div>
                </div>
            `;
        }
        
        statsGrid.innerHTML = statsHtml;
    }

    updateJobList(jobs) {
        const jobList = document.getElementById('jobList');
        
        if (jobs.length === 0) {
            jobList.innerHTML = `
                <div class="empty-state">
                    <div class="material-icons">inbox</div>
                    <p>No jobs yet. Submit your first image above!</p>
                    <p style="font-size: 12px; color: #999; margin-top: 8px;">
                        Only your own jobs are shown for privacy.
                    </p>
                </div>
            `;
            return;
        }

        const jobsHtml = jobs.map(job => {
            const createdAt = new Date(job.created_at).toLocaleString();
            const duration = job.duration_seconds ? `${job.duration_seconds.toFixed(1)}s` : '';
            
            let actionButtons = '';
            if (job.status === 'completed' && job.results_url) {
                actionButtons = `
                    <button class="btn-secondary btn" onclick="window.open('${job.results_url}', '_blank')" style="padding: 6px 12px; font-size: 12px;">
                        <span class="material-icons" style="font-size: 14px;">open_in_new</span>
                        View Results
                    </button>
                `;
            } else if (job.status === 'failed') {
                actionButtons = `
                    <button class="btn-secondary btn" onclick="alert('${job.error_message || 'Unknown error'}')" style="padding: 6px 12px; font-size: 12px;">
                        <span class="material-icons" style="font-size: 14px;">error</span>
                        Error Details
                    </button>
                `;
            }

            return `
                <div class="job-item">
                    <div class="job-info">
                        <div class="job-id">${job.job_id}</div>
                        <div>
                            <span class="job-status status-${job.status}">${job.status}</span>
                            ${job.metadata?.original_filename ? `<span style="margin-left: 8px; font-size: 12px; color: #666;">${job.metadata.original_filename}</span>` : ''}
                        </div>
                        <div style="font-size: 12px; color: #999; margin-top: 4px;">
                            ${createdAt} ${duration ? `• ${duration}` : ''}
                        </div>
                    </div>
                    <div class="job-actions">
                        ${actionButtons}
                    </div>
                </div>
            `;
        }).join('');

        jobList.innerHTML = jobsHtml;
    }

    showStatus(type, message) {
        const statusDiv = document.getElementById('submitStatus');
        statusDiv.innerHTML = `
            <div class="alert alert-${type === 'error' ? 'error' : 'success'}">
                ${message}
            </div>
        `;
        
        // Auto-clear success messages
        if (type === 'success') {
            setTimeout(() => this.clearStatus(), 5000);
        }
    }

    clearStatus() {
        document.getElementById('submitStatus').innerHTML = '';
    }

    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    startPolling() {
        // Poll for updates every 3 seconds
        this.pollInterval = setInterval(() => {
            this.refreshJobs();
        }, 3000);
    }

    stopPolling() {
        if (this.pollInterval) {
            clearInterval(this.pollInterval);
            this.pollInterval = null;
        }
    }
}

// Global functions for inline event handlers
function refreshJobs() {
    if (window.jobManager) {
        window.jobManager.refreshJobs();
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.jobManager = new JobManager();
});

// Handle page visibility for efficient polling
document.addEventListener('visibilitychange', () => {
    if (window.jobManager) {
        if (document.hidden) {
            window.jobManager.stopPolling();
        } else {
            window.jobManager.startPolling();
            window.jobManager.refreshJobs();
        }
    }
});