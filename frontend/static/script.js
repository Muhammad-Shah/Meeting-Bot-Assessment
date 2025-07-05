// Configuration
const API_BASE_URL = 'http://localhost:5000';
let sessionId = generateSessionId();

// Generate unique session ID
function generateSessionId() {
    return 'session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
}

// Upload transcript to backend
async function uploadTranscript() {
    const transcriptInput = document.getElementById('transcript-input');
    const uploadBtn = document.getElementById('upload-btn');
    const statusDiv = document.getElementById('upload-status');
    
    const transcript = transcriptInput.value.trim();
    
    if (!transcript) {
        showStatus('Please enter a transcript before uploading.', 'error');
        return;
    }
    
    uploadBtn.disabled = true;
    uploadBtn.textContent = 'Uploading...';
    showStatus('Uploading transcript...', 'info');
    
    try {
        const response = await fetch(`${API_BASE_URL}/upload`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                transcript: transcript,
                session_id: sessionId
            })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showStatus('Transcript uploaded successfully!', 'success');
            transcriptInput.value = '';
            addSystemMessage('Transcript uploaded. You can now ask questions about the meeting.');
        } else {
            showStatus(`Error: ${data.error || 'Failed to upload transcript'}`, 'error');
        }
    } catch (error) {
        showStatus(`Network error: ${error.message}`, 'error');
    } finally {
        uploadBtn.disabled = false;
        uploadBtn.textContent = 'Upload Transcript';
    }
}

// Send chat message
async function sendMessage() {
    const chatInput = document.getElementById('chat-input');
    const sendBtn = document.getElementById('send-btn');
    
    const message = chatInput.value.trim();
    
    if (!message) {
        return;
    }
    
    // Add user message to chat
    addMessage(message, 'user');
    chatInput.value = '';
    
    sendBtn.disabled = true;
    sendBtn.textContent = 'Sending...';
    
    try {
        const response = await fetch(`${API_BASE_URL}/chat`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                message: message,
                session_id: sessionId
            })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            addMessage(data.response, 'bot');
        } else {
            addMessage(`Error: ${data.error || 'Failed to get response'}`, 'error');
        }
    } catch (error) {
        addMessage(`Network error: ${error.message}`, 'error');
    } finally {
        sendBtn.disabled = false;
        sendBtn.textContent = 'Send';
    }
}

// Handle Enter key in chat input
function handleChatKeyPress(event) {
    if (event.key === 'Enter') {
        sendMessage();
    }
}

// Add message to chat UI
function addMessage(text, sender) {
    const chatMessages = document.getElementById('chat-messages');
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${sender}`;
    
    const timestamp = new Date().toLocaleTimeString();
    
    if (sender === 'user') {
        messageDiv.innerHTML = `
            <div class="message-header">You <span class="timestamp">${timestamp}</span></div>
            <div class="message-content">${escapeHtml(text)}</div>
        `;
    } else if (sender === 'bot') {
        messageDiv.innerHTML = `
            <div class="message-header">Assistant <span class="timestamp">${timestamp}</span></div>
            <div class="message-content">${escapeHtml(text)}</div>
        `;
    } else if (sender === 'error') {
        messageDiv.innerHTML = `
            <div class="message-header">Error <span class="timestamp">${timestamp}</span></div>
            <div class="message-content">${escapeHtml(text)}</div>
        `;
    }
    
    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Add system message
function addSystemMessage(text) {
    const chatMessages = document.getElementById('chat-messages');
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message system';
    
    const timestamp = new Date().toLocaleTimeString();
    messageDiv.innerHTML = `
        <div class="message-header">System <span class="timestamp">${timestamp}</span></div>
        <div class="message-content">${escapeHtml(text)}</div>
    `;
    
    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Show status message
function showStatus(message, type) {
    const statusDiv = document.getElementById('upload-status');
    statusDiv.textContent = message;
    statusDiv.className = `status-message ${type}`;
    
    // Clear status after 5 seconds for success/info messages
    if (type === 'success' || type === 'info') {
        setTimeout(() => {
            statusDiv.textContent = '';
            statusDiv.className = 'status-message';
        }, 5000);
    }
}

// Escape HTML to prevent XSS
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Initialize the app
document.addEventListener('DOMContentLoaded', function() {
    addSystemMessage(`Session started (ID: ${sessionId}). Upload a meeting transcript to begin.`);
});
