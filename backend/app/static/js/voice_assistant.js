// Voice RAG Assistant JavaScript Client with Full Continuous Lifecycle & Unlimited Multi-turn Interaction

let recognition = null;
let audioStream = null;
let mediaRecorder = null;
let isListening = false;
let isRecording = false;
let isSpeaking = false;
let isProcessing = false;
let currentTranscript = '';
let currentResponseText = '';

/**
 * Releases microphone hardware stream and completely resets recorder state.
 */
function releaseMicrophoneStream() {
  if (audioStream) {
    try {
      audioStream.getTracks().forEach(track => {
        if (track && typeof track.stop === 'function') {
          track.stop();
        }
      });
    } catch (e) {
      console.warn('Error releasing audio tracks:', e);
    }
    audioStream = null;
  }

  if (mediaRecorder) {
    try {
      if (mediaRecorder.state !== 'inactive') {
        mediaRecorder.stop();
      }
    } catch (e) {}
    mediaRecorder = null;
  }
}

/**
 * Completely resets recording state and clears recorder/stream references.
 */
function resetRecordingState() {
  releaseMicrophoneStream();

  if (recognition) {
    try {
      recognition.onstart = null;
      recognition.onresult = null;
      recognition.onerror = null;
      recognition.onend = null;
      recognition.abort();
    } catch (e) {}
    recognition = null;
  }

  isListening = false;
  isRecording = false;
}

function createSpeechRecognitionInstance() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) return null;

  const rec = new SpeechRecognition();
  rec.continuous = false;
  rec.interimResults = true;
  rec.lang = 'en-US';

  rec.onstart = () => {
    isListening = true;
    isRecording = true;
    updateVoiceMicUI();
  };

  rec.onresult = (event) => {
    const text = Array.from(event.results)
      .map(res => res[0].transcript)
      .join('');
    currentTranscript = text;

    const tEl = document.getElementById('voice-transcript-text');
    if (tEl) tEl.innerText = text;

    const submitBtn = document.getElementById('voice-submit-btn');
    if (submitBtn && text.trim()) submitBtn.classList.remove('hidden');
  };

  rec.onspeechend = () => {
    try { rec.stop(); } catch (e) {}
  };

  rec.onerror = (event) => {
    console.warn('Speech recognition error:', event.error);
    resetRecordingState();
    updateVoiceMicUI();

    if (event.error === 'not-allowed' || event.error === 'service-not-allowed') {
      alert('Microphone access was denied. Please check browser microphone permissions.');
    }
  };

  rec.onend = () => {
    resetRecordingState();
    updateVoiceMicUI();

    // Auto-trigger voice query processing if user spoke text and system is idle
    if (currentTranscript.trim() && !isProcessing && !isSpeaking) {
      sendVoiceQuery();
    }
  };

  return rec;
}

document.addEventListener('DOMContentLoaded', () => {
  updateVoiceMicUI();
});

function resetVoiceAssistantState() {
  stopVoiceSpeech();
  resetRecordingState();

  isSpeaking = false;
  isProcessing = false;
  currentTranscript = '';
  currentResponseText = '';

  const tEl = document.getElementById('voice-transcript-text');
  if (tEl) tEl.innerText = '';

  const submitBtn = document.getElementById('voice-submit-btn');
  if (submitBtn) submitBtn.classList.add('hidden');

  const resBox = document.getElementById('voice-response-box');
  if (resBox) resBox.classList.add('hidden');

  updateVoiceMicUI();
}

async function toggleVoiceListening() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition && !navigator.mediaDevices?.getUserMedia) {
    alert('Speech recognition is not supported in your browser.');
    return;
  }

  // Stop any active SpeechSynthesis playback immediately
  stopVoiceSpeech();

  if (isListening || isRecording) {
    resetRecordingState();
    updateVoiceMicUI();
    return;
  }

  // Reset state for a fresh voice turn
  currentTranscript = '';
  currentResponseText = '';
  isProcessing = false;
  resetRecordingState();

  const tEl = document.getElementById('voice-transcript-text');
  if (tEl) tEl.innerText = '';

  const submitBtn = document.getElementById('voice-submit-btn');
  if (submitBtn) submitBtn.classList.add('hidden');

  const resBox = document.getElementById('voice-response-box');
  if (resBox) resBox.classList.add('hidden');

  // Request audio stream to ensure microphone access is granted & tracked
  try {
    if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
      audioStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    }
  } catch (err) {
    console.warn('Microphone stream access warning:', err);
  }

  recognition = createSpeechRecognitionInstance();

  if (recognition) {
    try {
      recognition.start();
      isListening = true;
      isRecording = true;
    } catch (err) {
      console.error('Failed to start speech recognition:', err);
      resetRecordingState();
    }
  } else {
    resetRecordingState();
  }

  updateVoiceMicUI();
}

function updateVoiceMicUI() {
  const micBtn = document.getElementById('voice-mic-btn');
  const label = document.getElementById('voice-status-label');
  if (!micBtn || !label) return;

  // Guarantee the microphone button is permanently visible & clickable
  micBtn.style.display = 'flex';
  micBtn.style.visibility = 'visible';
  micBtn.style.opacity = '1';
  micBtn.disabled = isProcessing; // only disabled while API network request is in flight
  micBtn.classList.remove('hidden');

  // Preserve internal Lucide mic icon
  if (!micBtn.querySelector('svg') && !micBtn.querySelector('i')) {
    micBtn.innerHTML = '<i data-lucide="mic" class="w-10 h-10"></i>';
  }

  if (isListening || isRecording) {
    micBtn.className = 'w-24 h-24 rounded-full flex items-center justify-center transition-all duration-300 shadow-2xl relative bg-rose-600 text-white animate-pulse ring-8 ring-rose-500/30 scale-105 cursor-pointer';
    label.innerText = 'Listening... Tap to stop';
  } else if (isProcessing) {
    micBtn.className = 'w-24 h-24 rounded-full flex items-center justify-center transition-all duration-300 shadow-2xl relative bg-amber-600 text-white animate-pulse shadow-amber-600/50 cursor-pointer';
    label.innerText = 'Processing Voice Query...';
  } else if (isSpeaking) {
    micBtn.className = 'w-24 h-24 rounded-full flex items-center justify-center transition-all duration-300 shadow-2xl relative bg-emerald-600 text-white animate-pulse shadow-emerald-600/50 cursor-pointer';
    label.innerText = 'Speaking... Tap to interrupt';
  } else {
    micBtn.className = 'w-24 h-24 rounded-full flex items-center justify-center transition-all duration-300 shadow-2xl relative bg-indigo-600 hover:bg-indigo-500 text-white shadow-indigo-600/50 hover:scale-105 cursor-pointer';
    label.innerText = 'Tap Microphone to Speak';
  }

  if (window.lucide) {
    lucide.createIcons();
  }
}

async function sendVoiceQuery() {
  const queryText = currentTranscript.trim();
  if (!queryText || isProcessing) return;

  isProcessing = true;
  resetRecordingState();
  updateVoiceMicUI();

  const submitBtn = document.getElementById('voice-submit-btn');
  if (submitBtn) {
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<i data-lucide="loader-2" class="w-4 h-4 animate-spin"></i> Processing...';
    if (window.lucide) lucide.createIcons();
  }

  const resBox = document.getElementById('voice-response-box');
  const resText = document.getElementById('voice-response-text');
  if (resBox && resText) {
    resText.innerText = 'Thinking...';
    resBox.classList.remove('hidden');
  }

  currentResponseText = '';
  const token = typeof getAuthToken === 'function' ? getAuthToken() : '';

  try {
    const response = await fetch('/api/chat/stream', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({
        message: queryText,
        session_id: window.activeVoiceSessionId || 'voice_session'
      })
    });

    if (!response.ok) {
      if (resText) resText.innerText = 'Error processing voice query.';
      isProcessing = false;
      updateVoiceMicUI();
      return;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let buffer = '';

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n\n');
      buffer = lines.pop();

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const payload = JSON.parse(line.replace('data: ', '').trim());
            if (payload.token) {
              currentResponseText += payload.token;
              if (resText) resText.innerText = currentResponseText;
            }
          } catch (e) {
            console.error('SSE JSON parse error in voice client:', e);
          }
        }
      }
    }

    isProcessing = false;
    currentTranscript = ''; // Reset transcript for next turn

    if (currentResponseText.trim()) {
      speakVoiceText(currentResponseText);
    } else {
      isSpeaking = false;
      updateVoiceMicUI();
    }
  } catch (e) {
    console.error(e);
    if (resText) resText.innerText = 'Failed to process voice query.';
    isProcessing = false;
    isSpeaking = false;
    updateVoiceMicUI();
  } finally {
    isProcessing = false;
    currentTranscript = '';
    updateVoiceMicUI();
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.innerText = 'Process Voice Query';
    }
  }
}

function speakVoiceText(text) {
  if ('speechSynthesis' in window) {
    window.speechSynthesis.cancel();
    const cleanText = text.replace(/[*#`_]/g, '');
    const utterance = new SpeechSynthesisUtterance(cleanText);
    utterance.rate = 1.0;
    utterance.pitch = 1.0;

    utterance.onstart = () => {
      isSpeaking = true;
      isProcessing = false;
      updateVoiceMicUI();
      updateVoiceSpeechControls();
    };

    const handleSpeechEnd = () => {
      isSpeaking = false;
      isProcessing = false;
      isListening = false;
      isRecording = false;
      resetRecordingState();
      updateVoiceMicUI();
      updateVoiceSpeechControls();

      if (cleanText.includes("successfully published") || cleanText.includes("saved as a draft")) {
        if (window.location.pathname.includes('/exams')) {
          setTimeout(() => { window.location.reload(); }, 1200);
        }
      }
    };

    utterance.onend = handleSpeechEnd;
    utterance.onerror = handleSpeechEnd;

    window.speechSynthesis.speak(utterance);
  } else {
    isSpeaking = false;
    isProcessing = false;
    isListening = false;
    isRecording = false;
    resetRecordingState();
    updateVoiceMicUI();
  }
}

function stopVoiceSpeech() {
  if ('speechSynthesis' in window) {
    window.speechSynthesis.cancel();
  }
  isSpeaking = false;
  isProcessing = false;
  isListening = false;
  isRecording = false;
  resetRecordingState();
  updateVoiceMicUI();
  updateVoiceSpeechControls();
}

function updateVoiceSpeechControls() {
  const ctrl = document.getElementById('voice-speech-ctrl');
  if (!ctrl) return;

  if (isSpeaking) {
    ctrl.innerHTML = '<button onclick="stopVoiceSpeech()" class="text-rose-400 flex items-center gap-1 hover:underline"><i data-lucide="volume-x" class="w-3.5 h-3.5"></i> Stop Speaking</button>';
  } else {
    ctrl.innerHTML = '<button onclick="speakVoiceText(currentResponseText)" class="text-emerald-400 flex items-center gap-1 hover:underline"><i data-lucide="volume-2" class="w-3.5 h-3.5"></i> Replay Speech</button>';
  }
  if (window.lucide) lucide.createIcons();
}

window.startVoiceMockInterview = function(weekId, weekTitle) {
  window.activeVoiceSessionId = 'mock_interview_' + weekId;
  openModal('voice-assistant-modal');

  const titleEl = document.getElementById('voice-modal-title');
  if (titleEl) titleEl.innerText = `AI Voice Mock Interview (${weekTitle})`;

  const resText = document.getElementById('voice-response-text');
  const resBox = document.getElementById('voice-response-box');
  if (resBox && resText) {
    resText.innerText = `Initializing ${weekTitle} Mock Interview...`;
    resBox.classList.remove('hidden');
  }

  currentTranscript = "start";
  sendVoiceQuery();
};
