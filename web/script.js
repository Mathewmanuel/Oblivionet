// ===== OblivionNet Frontend JavaScript =====

class OblivionNetApp {
    constructor() {
        this.selectedFiles = [];
        this.currentTaskId = null;
        this.startTime = null;
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.setupDragAndDrop();
    }

    setupEventListeners() {
        // File input
        const fileInput = document.getElementById('fileInput');
        if (fileInput) {
            fileInput.addEventListener('change', (e) => {
                this.handleFileSelect(e.target.files);
            });
        }

        // Upload area click
        const uploadArea = document.getElementById('uploadArea');
        if (uploadArea) {
            uploadArea.addEventListener('click', () => {
                fileInput.click();
            });
        }

        // Process button
        const processBtn = document.getElementById('processBtn');
        if (processBtn) {
            processBtn.addEventListener('click', () => {
                this.startProcessing();
            });
        }

        // Navigation scroll
        window.scrollToUpload = () => {
            document.getElementById('upload').scrollIntoView({ 
                behavior: 'smooth' 
            });
        };
    }

    setupDragAndDrop() {
        const uploadArea = document.getElementById('uploadArea');
        if (!uploadArea) return;

        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            uploadArea.addEventListener(eventName, this.preventDefaults, false);
        });

        ['dragenter', 'dragover'].forEach(eventName => {
            uploadArea.addEventListener(eventName, () => {
                uploadArea.classList.add('dragover');
            });
        });

        ['dragleave', 'drop'].forEach(eventName => {
            uploadArea.addEventListener(eventName, () => {
                uploadArea.classList.remove('dragover');
            });
        });

        uploadArea.addEventListener('drop', (e) => {
            const files = e.dataTransfer.files;
            this.handleFileSelect(files);
        });
    }

    preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    handleFileSelect(files) {
        if (!files || files.length === 0) return;

        this.selectedFiles = Array.from(files).filter(file => this.isValidFile(file));
        
        if (this.selectedFiles.length === 0) {
            this.showNotification('Please select valid files (PDF, JPG, PNG, DOCX)', 'error');
            return;
        }

        this.updateUploadArea();
        this.enableProcessButton();
    }

    isValidFile(file) {
        const allowedTypes = [
            'application/pdf',
            'image/jpeg',
            'image/jpg', 
            'image/png',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        ];
        return allowedTypes.includes(file.type) || 
               file.name.toLowerCase().endsWith('.pdf') ||
               file.name.toLowerCase().endsWith('.jpg') ||
               file.name.toLowerCase().endsWith('.jpeg') ||
               file.name.toLowerCase().endsWith('.png') ||
               file.name.toLowerCase().endsWith('.docx');
    }

    updateUploadArea() {
        const uploadArea = document.getElementById('uploadArea');
        const uploadIcon = uploadArea.querySelector('.upload-icon i');
        const uploadTitle = uploadArea.querySelector('h3');
        const uploadDesc = uploadArea.querySelector('p');

        if (this.selectedFiles.length === 1) {
            uploadIcon.className = 'fas fa-file-check';
            uploadTitle.textContent = this.selectedFiles[0].name;
            uploadDesc.textContent = `${this.formatFileSize(this.selectedFiles[0].size)} - Ready to process`;
        } else {
            uploadIcon.className = 'fas fa-files';
            uploadTitle.textContent = `${this.selectedFiles.length} Files Selected`;
            uploadDesc.textContent = 'Multiple files ready for batch processing';
        }

        uploadArea.classList.add('files-selected');
    }

    enableProcessButton() {
        const processBtn = document.getElementById('processBtn');
        if (processBtn) {
            processBtn.disabled = false;
        }
    }

    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    getSelectedOptions() {
        // Get PII types
        const piiTypes = Array.from(document.querySelectorAll('input[name="pii-type"]:checked'))
            .map(cb => cb.value);

        // Get redaction method
        const redactionMethod = document.querySelector('input[name="redaction-method"]:checked')?.value || 'blackout';

        return {
            piiTypes,
            redactionMethod
        };
    }

    async startProcessing() {
        if (this.selectedFiles.length === 0) {
            this.showNotification('Please select files first', 'error');
            return;
        }

        this.startTime = Date.now();
        this.showProgressSection();
        this.updateProgress(0, 'Starting processing...');
        this.setStepActive('step1');

        try {
            const options = this.getSelectedOptions();
            const formData = new FormData();

            // Add files
            this.selectedFiles.forEach((file, index) => {
                formData.append(`files`, file);
            });

            // Add options
            formData.append('pii_types', JSON.stringify(options.piiTypes));
            formData.append('redaction_method', options.redactionMethod);

            this.updateProgress(10, 'Uploading files...');

            const response = await fetch('/api/upload', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                throw new Error(`Server error: ${response.status}`);
            }

            const data = await response.json();
            
            if (data.error) {
                throw new Error(data.error);
            }

            this.setStepActive('step2');
            this.updateProgress(25, 'Files uploaded successfully');

            if (data.task_id) {
                this.currentTaskId = data.task_id;
                this.checkProcessingStatus();
            } else {
                // Direct response
                this.handleProcessingComplete(data);
            }

        } catch (error) {
            console.error('Processing error:', error);
            this.showError('Processing failed: ' + error.message);
        }
    }

    async checkProcessingStatus() {
        if (!this.currentTaskId) return;

        try {
            const response = await fetch(`/api/status/${this.currentTaskId}`);
            const data = await response.json();

            if (data.error) {
                throw new Error(data.error);
            }

            this.updateProgress(data.progress || 30, data.message || 'Processing...');

            if (data.state === 'PENDING' || data.state === 'PROGRESS') {
                if (data.progress > 30) this.setStepActive('step3');
                setTimeout(() => this.checkProcessingStatus(), 2000);
            } else if (data.state === 'COMPLETED') {
                this.handleProcessingComplete(data);
            } else if (data.state === 'FAILED') {
                this.showError('Processing failed: ' + (data.message || 'Unknown error'));
            }

        } catch (error) {
            console.error('Status check error:', error);
            this.showError('Failed to check processing status');
        }
    }

    showProgressSection() {
        // Hide upload section
        document.getElementById('upload').style.display = 'none';
        
        // Show progress section
        const progressSection = document.getElementById('progressSection');
        if (progressSection) {
            progressSection.style.display = 'block';
        }
    }

    updateProgress(progress, message) {
        const progressFill = document.getElementById('progressFill');
        const progressText = document.getElementById('progressText');

        if (progressFill) {
            progressFill.style.width = `${progress}%`;
        }

        if (progressText) {
            progressText.textContent = `${this.selectedFiles.length} files - ${message}`;
        }
    }

    setStepActive(stepId) {
        // Remove active class from all steps
        document.querySelectorAll('.step').forEach(step => {
            step.classList.remove('active', 'completed');
        });

        // Add completed class to previous steps
        const steps = ['step1', 'step2', 'step3', 'step4'];
        const currentIndex = steps.indexOf(stepId);
        
        for (let i = 0; i < currentIndex; i++) {
            const step = document.getElementById(steps[i]);
            if (step) step.classList.add('completed');
        }

        // Add active class to current step
        const currentStep = document.getElementById(stepId);
        if (currentStep) currentStep.classList.add('active');
    }

    handleProcessingComplete(data) {
        const processingTime = this.startTime ? Math.round((Date.now() - this.startTime) / 1000) : 0;

        // Complete progress
        this.setStepActive('step4');
        this.updateProgress(100, 'Processing complete!');

        // Hide progress after delay and show results
        setTimeout(() => {
            document.getElementById('progressSection').style.display = 'none';
            this.showResults({
                filesProcessed: this.selectedFiles.length,
                piiDetected: data.total_pii_count || 0,
                processingTime: processingTime,
                results: data.results || []
            });
        }, 1500);
    }

    showResults(data) {
        const resultsSection = document.getElementById('resultsSection');
        const resultsGrid = document.getElementById('resultsGrid');
        
        if (!resultsSection || !resultsGrid) return;

        // Update summary stats
        const statElements = {
            'files-processed': data.filesProcessed,
            'pii-detected': data.piiDetected,
            'processing-time': data.processingTime + 's',
            'privacy-protected': '100%'
        };

        Object.entries(statElements).forEach(([id, value]) => {
            const element = document.getElementById(id);
            if (element) element.textContent = value;
        });

        // Create download links
        resultsGrid.innerHTML = '';
        
        if (data.results && data.results.length > 0) {
            data.results.forEach((result, index) => {
                const resultCard = this.createResultCard(result, index);
                resultsGrid.appendChild(resultCard);
            });
        } else {
            resultsGrid.innerHTML = '<p>No processed files available for download.</p>';
        }

        resultsSection.style.display = 'block';
    }

    createResultCard(result, index) {
        const card = document.createElement('div');
        card.className = 'result-card';
        
        const icon = this.getFileIcon(result.original_filename);
        
        card.innerHTML = `
            <div class="result-file">
                <i class="${icon}"></i>
                <h4>${result.original_filename}</h4>
                <p>PII Found: ${result.pii_count || 0}</p>
                ${result.output_file ? `
                    <a href="/api/download/${result.output_file}" 
                       class="btn btn-primary btn-sm" 
                       download>
                        <i class="fas fa-download"></i>
                        Download
                    </a>
                ` : '<p class="text-muted">Processing failed</p>'}
            </div>
        `;
        
        return card;
    }

    getFileIcon(filename) {
        const ext = filename.toLowerCase().split('.').pop();
        switch (ext) {
            case 'pdf': return 'fas fa-file-pdf';
            case 'jpg': case 'jpeg': case 'png': return 'fas fa-file-image';
            case 'docx': return 'fas fa-file-word';
            default: return 'fas fa-file';
        }
    }

    showError(message) {
        this.showNotification(message, 'error');
        
        // Reset interface
        setTimeout(() => {
            this.resetInterface();
        }, 3000);
    }

    showNotification(message, type = 'info') {
        // Create notification element
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.innerHTML = `
            <i class="fas fa-${type === 'error' ? 'exclamation-circle' : 'info-circle'}"></i>
            <span>${message}</span>
            <button class="notification-close">&times;</button>
        `;

        // Add to page
        document.body.appendChild(notification);

        // Auto remove after 5 seconds
        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        }, 5000);

        // Manual close
        notification.querySelector('.notification-close').addEventListener('click', () => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        });
    }

    resetInterface() {
        // Reset file selection
        this.selectedFiles = [];
        this.currentTaskId = null;
        
        // Reset upload area
        const uploadArea = document.getElementById('uploadArea');
        const fileInput = document.getElementById('fileInput');
        
        if (uploadArea) {
            uploadArea.classList.remove('files-selected');
            const uploadIcon = uploadArea.querySelector('.upload-icon i');
            const uploadTitle = uploadArea.querySelector('h3');
            const uploadDesc = uploadArea.querySelector('p');
            
            if (uploadIcon) uploadIcon.className = 'fas fa-cloud-upload-alt';
            if (uploadTitle) uploadTitle.textContent = 'Drop files here or click to browse';
            if (uploadDesc) uploadDesc.textContent = 'Supports PDF, JPG, PNG, DOCX, and more';
        }
        
        if (fileInput) fileInput.value = '';
        
        // Reset process button
        const processBtn = document.getElementById('processBtn');
        if (processBtn) processBtn.disabled = true;
        
        // Hide sections
        document.getElementById('progressSection').style.display = 'none';
        document.getElementById('resultsSection').style.display = 'none';
        document.getElementById('upload').style.display = 'block';
    }
}

// Smooth scrolling function
function scrollToUpload() {
    document.getElementById('upload').scrollIntoView({ 
        behavior: 'smooth' 
    });
}

// CSS for notifications
const notificationStyles = `
.notification {
    position: fixed;
    top: 20px;
    right: 20px;
    background: white;
    padding: 1rem 1.5rem;
    border-radius: 8px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    display: flex;
    align-items: center;
    gap: 0.75rem;
    z-index: 1000;
    min-width: 300px;
    animation: slideIn 0.3s ease;
}

.notification.error {
    border-left: 4px solid #dc3545;
    background: #fff5f5;
}

.notification.info {
    border-left: 4px solid #007bff;
    background: #f8f9ff;
}

.notification i {
    font-size: 1.2rem;
}

.notification.error i {
    color: #dc3545;
}

.notification.info i {
    color: #007bff;
}

.notification-close {
    background: none;
    border: none;
    font-size: 1.5rem;
    cursor: pointer;
    padding: 0;
    margin-left: auto;
    color: #666;
}

.notification-close:hover {
    color: #333;
}

@keyframes slideIn {
    from {
        transform: translateX(100%);
        opacity: 0;
    }
    to {
        transform: translateX(0);
        opacity: 1;
    }
}

.files-selected {
    border-color: #4F46E5 !important;
    background: #f0f4ff !important;
}

.result-card {
    background: white;
    border-radius: 12px;
    padding: 1.5rem;
    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    text-align: center;
}

.result-file i {
    font-size: 2rem;
    margin-bottom: 1rem;
}

.result-file h4 {
    margin: 0.5rem 0;
    font-size: 1rem;
    color: #333;
}

.result-file p {
    color: #666;
    margin: 0.5rem 0;
}

.btn-sm {
    padding: 0.5rem 1rem;
    font-size: 0.875rem;
}
`;

// Add notification styles to page
const styleSheet = document.createElement('style');
styleSheet.textContent = notificationStyles;
document.head.appendChild(styleSheet);

// Initialize app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.oblivionApp = new OblivionNetApp();
});