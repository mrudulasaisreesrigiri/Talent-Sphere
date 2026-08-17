import React, { useState, useRef, useEffect } from 'react';
import { Mic, MicOff, Volume2, VolumeX, X, Sparkles, Loader2 } from 'lucide-react';
import { apiClient } from '../api/client';

interface VoiceAssistantModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const VoiceAssistantModal: React.FC<VoiceAssistantModalProps> = ({ isOpen, onClose }) => {
  const [isListening, setIsListening] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [transcript, setTranscript] = useState('');
  const [response, setResponse] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  // References to eliminate stale closure bugs across async voice/speech lifecycles
  const recognitionRef = useRef<any>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const utteranceRef = useRef<SpeechSynthesisUtterance | null>(null);
  const transcriptRef = useRef<string>('');
  const isProcessingRef = useRef<boolean>(false);
  const isSpeakingRef = useRef<boolean>(false);

  // Sync ref with transcript state
  useEffect(() => {
    transcriptRef.current = transcript;
  }, [transcript]);

  // Clean up when modal unmounts or closes
  useEffect(() => {
    return () => {
      stopSpeaking();
      resetRecordingState();
    };
  }, []);

  if (!isOpen) return null;

  /**
   * Releases microphone hardware stream by stopping all tracks
   */
  const releaseMicrophoneStream = () => {
    if (streamRef.current) {
      try {
        streamRef.current.getTracks().forEach((track) => {
          if (track && typeof track.stop === 'function') {
            track.stop();
          }
        });
      } catch (e) {
        console.warn('Error releasing audio tracks:', e);
      }
      streamRef.current = null;
    }
  };

  /**
   * Completely resets recording state and clears recorder/stream references
   */
  const resetRecordingState = () => {
    releaseMicrophoneStream();

    if (recognitionRef.current) {
      try {
        recognitionRef.current.onstart = null;
        recognitionRef.current.onresult = null;
        recognitionRef.current.onerror = null;
        recognitionRef.current.onend = null;
        recognitionRef.current.abort();
      } catch (e) {}
      recognitionRef.current = null;
    }

    setIsListening(false);
    setIsRecording(false);
  };

  /**
   * Creates a fresh SpeechRecognition instance
   */
  const createRecognitionInstance = () => {
    if (!('webkitSpeechRecognition' in window || 'SpeechRecognition' in window)) {
      return null;
    }
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    const recog = new SpeechRecognition();
    recog.continuous = false;
    recog.interimResults = true;
    recog.lang = 'en-US';

    recog.onstart = () => {
      setIsListening(true);
      setIsRecording(true);
    };

    recog.onresult = (event: any) => {
      const text = Array.from(event.results)
        .map((res: any) => res[0].transcript)
        .join('');
      setTranscript(text);
      transcriptRef.current = text;
    };

    recog.onspeechend = () => {
      try { recog.stop(); } catch (e) {}
    };

    recog.onerror = (err: any) => {
      console.warn('Speech recognition event error:', err);
      resetRecordingState();
    };

    recog.onend = () => {
      resetRecordingState();
      // Auto-trigger voice query submission if speech text was transcribed
      const currentText = transcriptRef.current.trim();
      if (currentText && !isProcessingRef.current && !isSpeakingRef.current) {
        handleSendVoiceQuery(currentText);
      }
    };

    return recog;
  };

  /**
   * Stops active speech synthesis playback
   */
  const stopSpeaking = () => {
    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel();
    }
    utteranceRef.current = null;
    setIsSpeaking(false);
    isSpeakingRef.current = false;
    resetRecordingState();
  };

  /**
   * Toggles voice listening on microphone tap
   */
  const toggleListening = () => {
    stopSpeaking();

    if (isListening || isRecording) {
      resetRecordingState();
      return;
    }

    setTranscript('');
    transcriptRef.current = '';
    setResponse('');
    setIsLoading(false);
    isProcessingRef.current = false;
    resetRecordingState();

    const recog = createRecognitionInstance();
    if (!recog) {
      alert('Speech recognition is not supported in your browser. Please use Google Chrome, Edge, or Brave.');
      resetRecordingState();
      return;
    }

    recognitionRef.current = recog;
    try {
      recog.start();
      setIsListening(true);
      setIsRecording(true);
    } catch (err) {
      console.error('Failed to start speech recognition:', err);
      resetRecordingState();
    }
  };

  /**
   * Sends voice query to Flask Backend /api/chat
   */
  const handleSendVoiceQuery = async (customQuery?: string) => {
    const queryText = (customQuery || transcript || transcriptRef.current).trim();
    if (!queryText || isProcessingRef.current) return;

    setIsLoading(true);
    isProcessingRef.current = true;
    resetRecordingState();

    try {
      const res = await apiClient.post('/chat', {
        message: queryText,
        session_id: 'voice_session'
      });
      const aiMessage = res.data.message;
      setResponse(aiMessage);
      setTranscript('');
      transcriptRef.current = '';
      speakText(aiMessage);
    } catch (e) {
      console.error('Error sending voice query to backend:', e);
      setResponse('Failed to process voice query. Please check connection and try again.');
      resetRecordingState();
    } finally {
      setIsLoading(false);
      isProcessingRef.current = false;
    }
  };

  /**
   * Speaks AI response using browser Text-to-Speech
   */
  const speakText = (text: string) => {
    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel();
      const cleanText = text.replace(/[*#`_]/g, '');
      const utterance = new SpeechSynthesisUtterance(cleanText);
      utterance.rate = 1.0;
      utterance.pitch = 1.0;
      utteranceRef.current = utterance;

      utterance.onstart = () => {
        setIsSpeaking(true);
        isSpeakingRef.current = true;
      };

      const handleEnd = () => {
        utteranceRef.current = null;
        setIsSpeaking(false);
        isSpeakingRef.current = false;
        setIsListening(false);
        setIsRecording(false);
        setIsLoading(false);
        isProcessingRef.current = false;
        resetRecordingState();
      };

      utterance.onend = handleEnd;
      utterance.onerror = handleEnd;

      window.speechSynthesis.speak(utterance);
    } else {
      setIsSpeaking(false);
      isSpeakingRef.current = false;
      resetRecordingState();
    }
  };

  const handleModalClose = () => {
    stopSpeaking();
    resetRecordingState();
    setIsSpeaking(false);
    isSpeakingRef.current = false;
    setIsLoading(false);
    isProcessingRef.current = false;
    setTranscript('');
    transcriptRef.current = '';
    setResponse('');
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-md animate-fade-in">
      <div className="glass-panel w-full max-w-lg rounded-3xl border border-indigo-500/30 p-6 shadow-2xl relative overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-800 pb-4 mb-6">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-indigo-600/20 text-indigo-400 border border-indigo-500/30">
              <Sparkles className="w-5 h-5 animate-spin-slow" />
            </div>
            <div>
              <h3 className="font-bold text-white text-base">Voice RAG Assistant</h3>
              <p className="text-xs text-slate-400">Push-to-Talk AI Voice Companion</p>
            </div>
          </div>
          <button
            onClick={handleModalClose}
            className="p-2 rounded-xl text-slate-400 hover:text-white hover:bg-slate-800 transition-colors cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Visual Microphone Container */}
        <div className="flex flex-col items-center justify-center my-8 gap-4">
          <button
            onClick={toggleListening}
            disabled={isLoading}
            className={`w-24 h-24 rounded-full flex items-center justify-center transition-all duration-300 shadow-2xl relative cursor-pointer ${
              isListening || isRecording
                ? 'bg-rose-600 text-white animate-pulse ring-8 ring-rose-500/30 scale-105'
                : isLoading
                ? 'bg-amber-600 text-white animate-pulse shadow-amber-600/50'
                : isSpeaking
                ? 'bg-emerald-600 text-white animate-pulse shadow-emerald-600/50'
                : 'bg-indigo-600 hover:bg-indigo-500 text-white shadow-indigo-600/50 hover:scale-105'
            }`}
          >
            {isListening || isRecording ? <MicOff className="w-10 h-10" /> : <Mic className="w-10 h-10" />}
          </button>
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
            {isListening || isRecording
              ? 'Listening... Tap to stop'
              : isLoading
              ? 'Processing Voice Query...'
              : isSpeaking
              ? 'Speaking... Tap to interrupt'
              : 'Tap Microphone to Speak'}
          </span>
        </div>

        {/* Transcript Box */}
        {transcript && (
          <div className="mb-4 p-3.5 rounded-xl bg-slate-900/80 border border-slate-800">
            <p className="text-xs font-semibold text-slate-400 mb-1">Your Voice Query:</p>
            <p className="text-sm text-indigo-300 font-medium">{transcript}</p>

            {!isListening && !isRecording && transcript && (
              <button
                onClick={() => handleSendVoiceQuery()}
                disabled={isLoading}
                className="mt-3 w-full py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-xs flex items-center justify-center gap-2 cursor-pointer"
              >
                {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Process Voice Query'}
              </button>
            )}
          </div>
        )}

        {/* AI Response Display */}
        {response && (
          <div className="p-4 rounded-2xl bg-indigo-950/40 border border-indigo-500/20 text-slate-200 text-xs leading-relaxed max-h-40 overflow-y-auto">
            <div className="flex items-center justify-between mb-2">
              <span className="font-bold text-indigo-400">AI Response:</span>
              {isSpeaking ? (
                <button onClick={stopSpeaking} className="text-rose-400 flex items-center gap-1 hover:underline cursor-pointer">
                  <VolumeX className="w-3.5 h-3.5" /> Stop Speaking
                </button>
              ) : (
                <button onClick={() => speakText(response)} className="text-emerald-400 flex items-center gap-1 hover:underline cursor-pointer">
                  <Volume2 className="w-3.5 h-3.5" /> Replay Speech
                </button>
              )}
            </div>
            <p>{response}</p>
          </div>
        )}
      </div>
    </div>
  );
};
