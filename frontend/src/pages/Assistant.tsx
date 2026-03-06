import React, { useState, useRef, useEffect } from "react";
import { Link, useNavigate, useLocation } from "react-router-dom";
import {
  ArrowLeft,
  History,
  Bot,
  User,
  Image as ImageIcon,
  Mic,
  Send,
  SkipForward,
  Play,
  Square,
  Loader2,
  Languages,
  Globe,
  Volume2,
  VolumeX,
} from "lucide-react";
import BottomNav from "../components/BottomNav";

// ── Markdown renderer ─────────────────────────────────────────────────────────
function renderMarkdown(text: string): React.ReactNode[] {
  // Safety check: handle undefined or null text
  if (!text || typeof text !== 'string') {
    return [];
  }
  
  const lines = text.split("\n");
  const nodes: React.ReactNode[] = [];

  const inlineParse = (raw: string, key: string): React.ReactNode => {
    // Handle **bold** and *italic*
    const parts = raw.split(/(\*\*[^*]+\*\*|\*[^*]+\*)/g);
    return (
      <span key={key}>
        {parts.map((p, i) => {
          if (p.startsWith("**") && p.endsWith("**"))
            return <strong key={i}>{p.slice(2, -2)}</strong>;
          if (p.startsWith("*") && p.endsWith("*"))
            return <em key={i}>{p.slice(1, -1)}</em>;
          return p;
        })}
      </span>
    );
  };

  lines.forEach((line, idx) => {
    const k = String(idx);
    if (/^###\s/.test(line)) {
      nodes.push(
        <p key={k} className="font-bold text-primary text-sm mb-1">
          {line.replace(/^###\s/, "")}
        </p>,
      );
    } else if (/^##\s/.test(line)) {
      nodes.push(
        <p key={k} className="font-bold text-slate-800 text-sm mb-1">
          {line.replace(/^##\s/, "")}
        </p>,
      );
    } else if (/^[-*]\s/.test(line)) {
      nodes.push(
        <p key={k} className="text-sm flex gap-1 mb-0.5">
          <span className="text-primary shrink-0 mt-0.5">•</span>
          {inlineParse(line.replace(/^[-*]\s/, ""), k + "c")}
        </p>,
      );
    } else if (line.trim() === "") {
      nodes.push(<div key={k} className="h-2" />);
    } else {
      nodes.push(
        <p key={k} className="text-sm leading-relaxed mb-0.5">
          {inlineParse(line, k + "c")}
        </p>,
      );
    }
  });

  return nodes;
}

// ── Option extractor ──────────────────────────────────────────────────────────
// Returns an array of short clickable option strings detected in the message.
function extractOptions(text: string): string[] {
  const options: string[] = [];

  // Detect bullet / numbered list items  e.g.  "- Job" or "1. Plumbing"
  const bulletLines = text.match(/^[-*1-9][.)\s]\s*(.+)$/gm) || [];
  if (bulletLines.length >= 2) {
    bulletLines.forEach((l) => {
      const clean = l
        .replace(/^[-*1-9][.)\s]\s*/, "")
        .replace(/\*\*/g, "")
        .replace(/,?\s*or\s*$/i, "")  // strip trailing ", or"
        .replace(/[,?.]$/, "")          // strip trailing punctuation
        .trim();
      if (clean.length > 0 && clean.length < 150) options.push(clean);
    });
    return options;
  }

  // For bold and e.g. detection, only scan the LAST paragraph.
  // This prevents names bolded in greetings (e.g. "welcome, **Ganesh**!")
  // from being picked up as options alongside real choices.
  const paragraphs = text.split(/\n\n+/).filter((p) => p.trim().length > 0);
  const searchText = paragraphs.length > 1 ? paragraphs[paragraphs.length - 1] : text;

  // Detect bold text options: **option1**, **option2**, or **option3**
  const boldMatches = searchText.match(/\*\*([^*]+)\*\*/g);
  if (boldMatches && boldMatches.length >= 2) {
    const boldOptions = boldMatches
      .map((m) => m.replace(/\*\*/g, "").trim())
      .filter((s) => s.length > 0 && s.length < 80);
    if (boldOptions.length >= 2) return boldOptions;
  }

  // Detect  "e.g., A, B or C" or "(e.g., A, B, C)"
  const egMatch = searchText.match(/(?:e\.g[.,]|for example)[,:]?\s*([^?.!\n]+)/i);
  if (egMatch) {
    const raw = egMatch[1].replace(/[()]/g, "");
    const parts = raw
      .split(/,|\s+or\s+/)
      .map((s) => s.replace(/\*\*/g, "").trim())
      .filter((s) => s.length > 0 && s.length < 80);
    if (parts.length >= 2) return parts;
  }

  return [];
}

const API_BASE = import.meta.env.VITE_API_URL ? `${import.meta.env.VITE_API_URL}/api` : "http://localhost:8000/api";

// Generate a stable session_id for this browser session
// Fallback for browsers that don't support crypto.randomUUID (older browsers or HTTP context)
const generateUUID = () => {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  // Fallback: simple random ID
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = Math.random() * 16 | 0;
    const v = c === 'x' ? r : (r & 0x3 | 0x8);
    return v.toString(16);
  });
};

const getSessionId = () => {
  let id = sessionStorage.getItem("swavalambi_session_id");
  if (!id) {
    id = generateUUID();
    sessionStorage.setItem("swavalambi_session_id", id);
  }
  return id;
};

// Clear session for reassessment
const clearSession = () => {
  sessionStorage.removeItem("swavalambi_session_id");
  // Generate new session ID
  const newId = generateUUID();
  sessionStorage.setItem("swavalambi_session_id", newId);
  return newId;
};

interface Message {
  id: string;
  role: "assistant" | "user";
  content: string;
  isReadyForPhoto?: boolean;
  imagePreviewUrl?: string;
}

// PlaybackButton Component
interface PlaybackButtonProps {
  messageId: string;
  messageText: string;
  isLoading: boolean;
  isPlaying: boolean;
  onPlay: () => void;
  onStop: () => void;
}

const PlaybackButton: React.FC<PlaybackButtonProps> = ({
  messageId,
  messageText,
  isLoading,
  isPlaying,
  onPlay,
  onStop,
}) => {
  const handleClick = () => {
    if (isPlaying) {
      onStop();
    } else {
      onPlay();
    }
  };

  return (
    <button
      onClick={handleClick}
      disabled={isLoading}
      className={`w-8 h-8 rounded-full flex items-center justify-center transition-all duration-150 ${
        isPlaying
          ? "bg-primary/20 border border-primary/30 animate-pulse"
          : "bg-primary/10 border border-primary/20 hover:bg-primary/15 hover:scale-105"
      } ${isLoading ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}`}
      aria-label={isPlaying ? "Stop audio" : "Play audio"}
      title={isPlaying ? "Stop" : "Play"}
    >
      {isLoading ? (
        <Loader2 size={14} className="text-primary animate-spin" />
      ) : isPlaying ? (
        <Square size={14} className="text-primary fill-current" />
      ) : (
        <Play size={14} className="text-primary fill-current" />
      )}
    </button>
  );
};

export default function Assistant() {
  const navigate = useNavigate();
  const location = useLocation();
  const sessionId = getSessionId();
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoadingHistory, setIsLoadingHistory] = useState(true);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [mediaRecorder, setMediaRecorder] = useState<MediaRecorder | null>(null);
  const [selectedLanguage, setSelectedLanguage] = useState("hi-IN");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const hasPlayedGreetingRef = useRef(false); // Use ref instead of state for immediate persistence
  const hasSavedInitialGreetingRef = useRef(false); // Prevent duplicate greeting saves

  // Playback state for voice playback controls
  const [playingMessageId, setPlayingMessageId] = useState<string | null>(null);
  const [currentAudio, setCurrentAudio] = useState<HTMLAudioElement | null>(null);
  const [isLoadingAudio, setIsLoadingAudio] = useState<string | null>(null);

  // Redirect countdown modal state
  const [showRedirectModal, setShowRedirectModal] = useState(false);
  const [redirectCountdown, setRedirectCountdown] = useState(5);
  const [redirectPath, setRedirectPath] = useState("");
  const redirectTimerRef = useRef<NodeJS.Timeout | null>(null);

  // Clear chat confirmation modal state
  const [showClearChatModal, setShowClearChatModal] = useState(false);

  // Language selection modal state
  const [showLanguageModal, setShowLanguageModal] = useState(false);
  const [showLanguageSelector, setShowLanguageSelector] = useState(false);

  // Voice auto-play toggle state (default: enabled for better voice UX)
  const [voiceAutoPlay, setVoiceAutoPlay] = useState(true);

  // Supported languages
  const languages = [
    { code: "hi-IN", name: "हिंदी", nativeName: "Hindi", flag: "🇮🇳" },
    { code: "te-IN", name: "తెలుగు", nativeName: "Telugu", flag: "🇮🇳" },
    { code: "ta-IN", name: "தமிழ்", nativeName: "Tamil", flag: "🇮🇳" },
    { code: "mr-IN", name: "मराठी", nativeName: "Marathi", flag: "🇮🇳" },
    { code: "kn-IN", name: "ಕನ್ನಡ", nativeName: "Kannada", flag: "🇮🇳" },
    { code: "bn-IN", name: "বাংলা", nativeName: "Bengali", flag: "🇮🇳" },
    { code: "gu-IN", name: "ગુજરાતી", nativeName: "Gujarati", flag: "🇮🇳" },
    { code: "ml-IN", name: "മലയാളം", nativeName: "Malayalam", flag: "🇮🇳" },
    { code: "pa-IN", name: "ਪੰਜਾਬੀ", nativeName: "Punjabi", flag: "🇮🇳" },
    { code: "en-IN", name: "English", nativeName: "English", flag: "🇬🇧" },
  ];

  // Multilingual greetings
  const getGreeting = (langCode: string, userName: string) => {
    const greetings: Record<string, { withName: string; withoutName: string }> = {
      "hi-IN": {
        withName: `नमस्ते, ${userName}! 😊 मैं आपका स्वावलंबी सहायक हूं। आइए आपकी प्रोफाइल बनाएं। आप किस तरह का काम करते हैं? (जैसे, **दर्जी**, **बढ़ई**, **प्लंबर**, **वेल्डर**, **ब्यूटीशियन**)`,
        withoutName: `नमस्ते! मैं आपका स्वावलंबी सहायक हूं। आइए आपकी प्रोफाइल बनाएं। बताइए, आप किस तरह का काम करते हैं? (जैसे, **दर्जी**, **बढ़ई**, **प्लंबर**, **वेल्डर**, **ब्यूटीशियन**)`
      },
      "te-IN": {
        withName: `నమస్తే, ${userName}! 😊 నేను మీ స్వావలంబి సహాయకుడిని। మీ ప్రొఫైల్ రూపొందించుకుందాం. మీరు ఏ రకమైన పని చేస్తారు? (ఉదా., **టైలర్**, **కార్పెంటర్**, **ప్లంబర్**, **వెల్డర్**, **బ్యూటీషియన్**)`,
        withoutName: `నమస్తే! నేను మీ స్వావలంబి సహాయకుడిని. మీ ప్రొఫైల్ రూపొందించుకుందాం. చెప్పండి, మీరు ఏ రకమైన పని చేస్తారు? (ఉదా., **టైలర్**, **కార్పెంటర్**, **ప్లంబర్**, **వెల్డర్**, **బ్యూటీషియన్**)`
      },
      "ta-IN": {
        withName: `வணக்கம், ${userName}! 😊 நான் உங்கள் ஸ்வாவலம்பி உதவியாளர். உங்கள் சுயவிவரத்தை உருவாக்குவோம். நீங்கள் என்ன வேலை செய்கிறீர்கள்? (எ.கா., **தையல்காரர்**, **தச்சர்**, **பிளம்பர்**, **வெல்டர்**, **அழகுக் கலைஞர்**)`,
        withoutName: `வணக்கம்! நான் உங்கள் ஸ்வாவலம்பி உதவியாளர். உங்கள் சுயவிவரத்தை உருவாக்குவோம். சொல்லுங்கள், நீங்கள் என்ன வேலை செய்கிறீர்கள்? (எ.கா., **தையல்காரர்**, **தச்சர்**, **பிளம்பர்**, **வெல்டர்**, **அழகுக் கலைஞர்**)`
      },
      "mr-IN": {
        withName: `नमस्कार, ${userName}! 😊 मी तुमचा स्वावलंबी सहाय्यक आहे. चला तुमचे प्रोफाइल तयार करूया. तुम्ही कोणत्या प्रकारचे काम करता? (उदा., **शिंपी**, **सुतार**, **प्लंबर**, **वेल्डर**, **ब्युटिशियन**)`,
        withoutName: `नमस्कार! मी तुमचा स्वावलंबी सहाय्यक आहे. चला तुमचे प्रोफाइल तयार करूया. सांगा, तुम्ही कोणत्या प्रकारचे काम करता? (उदा., **शिंपी**, **सुतार**, **प्लंबर**, **वेल्डर**, **ब्युटिशियन**)`
      },
      "kn-IN": {
        withName: `ನಮಸ್ಕಾರ, ${userName}! 😊 ನಾನು ನಿಮ್ಮ ಸ್ವಾವಲಂಬಿ ಸಹಾಯಕ. ನಿಮ್ಮ ಪ್ರೊಫೈಲ್ ರಚಿಸೋಣ. ನೀವು ಯಾವ ರೀತಿಯ ಕೆಲಸ ಮಾಡುತ್ತೀರಿ? (ಉದಾ., **ಟೈಲರ್**, **ಬಡಗಿ**, **ಪ್ಲಂಬರ್**, **ವೆಲ್ಡರ್**, **ಬ್ಯೂಟಿಶಿಯನ್**)`,
        withoutName: `ನಮಸ್ಕಾರ! ನಾನು ನಿಮ್ಮ ಸ್ವಾವಲಂಬಿ ಸಹಾಯಕ. ನಿಮ್ಮ ಪ್ರೊಫೈಲ್ ರಚಿಸೋಣ. ಹೇಳಿ, ನೀವು ಯಾವ ರೀತಿಯ ಕೆಲಸ ಮಾಡುತ್ತೀರಿ? (ಉದಾ., **ಟೈಲರ್**, **ಬಡಗಿ**, **ಪ್ಲಂಬರ್**, **ವೆಲ್ಡರ್**, **ಬ್ಯೂಟಿಶಿಯನ್**)`
      },
      "bn-IN": {
        withName: `নমস্কার, ${userName}! 😊 আমি আপনার স্বাবলম্বী সহায়ক। আসুন আপনার প্রোফাইল তৈরি করি। আপনি কী ধরনের কাজ করেন? (যেমন, **দর্জি**, **ছুতোর**, **প্লাম্বার**, **ওয়েল্ডার**, **বিউটিশিয়ান**)`,
        withoutName: `নমস্কার! আমি আপনার স্বাবলম্বী সহায়ক। আসুন আপনার প্রোফাইল তৈরি করি। বলুন, আপনি কী ধরনের কাজ করেন? (যেমন, **দর্জি**, **ছুতোর**, **প্লাম্বার**, **ওয়েল্ডার**, **বিউটিশিয়ান**)`
      },
      "gu-IN": {
        withName: `નમસ્તે, ${userName}! 😊 હું તમારો સ્વાવલંબી સહાયક છું. ચાલો તમારી પ્રોફાઇલ બનાવીએ. તમે કેવા પ્રકારનું કામ કરો છો? (દા.ત., **દરજી**, **સુથાર**, **પ્લમ્બર**, **વેલ્ડર**, **બ્યુટિશિયન**)`,
        withoutName: `નમસ્તે! હું તમારો સ્વાવલંબી સહાયક છું. ચાલો તમારી પ્રોફાઇલ બનાવીએ. કહો, તમે કેવા પ્રકારનું કામ કરો છો? (દા.ત., **દરજી**, **સુથાર**, **પ્લમ્બર**, **વેલ્ડર**, **બ્યુટિશિયન**)`
      },
      "ml-IN": {
        withName: `നമസ്കാരം, ${userName}! 😊 ഞാൻ നിങ്ങളുടെ സ്വാവലംബി സഹായകനാണ്. നിങ്ങളുടെ പ്രൊഫൈൽ സൃഷ്ടിക്കാം. നിങ്ങൾ ഏത് തരത്തിലുള്ള ജോലി ചെയ്യുന്നു? (ഉദാ., **ടെയിലർ**, **ആശാരി**, **പ്ലംബർ**, **വെൽഡർ**, **ബ്യൂട്ടീഷ്യൻ**)`,
        withoutName: `നമസ്കാരം! ഞാൻ നിങ്ങളുടെ സ്വാവലംബി സഹായകനാണ്. നിങ്ങളുടെ പ്രൊഫൈൽ സൃഷ്ടിക്കാം. പറയൂ, നിങ്ങൾ ഏത് തരത്തിലുള്ള ജോലി ചെയ്യുന്നു? (ഉദാ., **ടെയിലർ**, **ആശാരി**, **പ്ലംബർ**, **വെൽഡർ**, **ബ്യൂട്ടീഷ്യൻ**)`
      },
      "pa-IN": {
        withName: `ਸਤ ਸ੍ਰੀ ਅਕਾਲ, ${userName}! 😊 ਮੈਂ ਤੁਹਾਡਾ ਸਵਾਵਲੰਬੀ ਸਹਾਇਕ ਹਾਂ। ਆਓ ਤੁਹਾਡੀ ਪ੍ਰੋਫਾਈਲ ਬਣਾਈਏ। ਤੁਸੀਂ ਕਿਸ ਤਰ੍ਹਾਂ ਦਾ ਕੰਮ ਕਰਦੇ ਹੋ? (ਜਿਵੇਂ, **ਦਰਜ਼ੀ**, **ਤਰਖਾਣ**, **ਪਲੰਬਰ**, **ਵੈਲਡਰ**, **ਬਿਊਟੀਸ਼ੀਅਨ**)`,
        withoutName: `ਸਤ ਸ੍ਰੀ ਅਕਾਲ! ਮੈਂ ਤੁਹਾਡਾ ਸਵਾਵਲੰਬੀ ਸਹਾਇਕ ਹਾਂ। ਆਓ ਤੁਹਾਡੀ ਪ੍ਰੋਫਾਈਲ ਬਣਾਈਏ। ਦੱਸੋ, ਤੁਸੀਂ ਕਿਸ ਤਰ੍ਹਾਂ ਦਾ ਕੰਮ ਕਰਦੇ ਹੋ? (ਜਿਵੇਂ, **ਦਰਜ਼ੀ**, **ਤਰਖਾਣ**, **ਪਲੰਬਰ**, **ਵੈਲਡਰ**, **ਬਿਊਟੀਸ਼ੀਅਨ**)`
      },
      "en-IN": {
        withName: `Namaste, ${userName}! 😊 I'm your Swavalambi Assistant. Let's build your profile. What kind of work do you do? (e.g., **Tailor**, **Carpenter**, **Plumber**, **Welder**, **Beautician**)`,
        withoutName: `Namaste! I am your Swavalambi assistant. Let's build your profile. Tell me, what kind of work do you do? (e.g., **Tailor**, **Carpenter**, **Plumber**, **Welder**, **Beautician**)`
      }
    };

    const greeting = greetings[langCode] || greetings["en-IN"];
    return userName ? greeting.withName : greeting.withoutName;
  };

  // Initialize language and voice preferences
  useEffect(() => {
    const initializePreferences = async () => {
      const userId = localStorage.getItem("swavalambi_user_id");
      
      // Try to load from backend first if user is logged in
      if (userId) {
        try {
          const res = await fetch(`${API_BASE}/users/${userId}`);
          if (res.ok) {
            const userData = await res.json();
            
            // Load language preference from backend
            if (userData.preferred_language) {
              setSelectedLanguage(userData.preferred_language);
              localStorage.setItem("swavalambi_language", userData.preferred_language);
            } else {
              // Fallback to localStorage
              const storedLanguage = localStorage.getItem("swavalambi_language");
              if (storedLanguage) {
                setSelectedLanguage(storedLanguage);
              } else {
                // Show language selection modal on first visit
                setShowLanguageModal(true);
              }
            }
            
            // Load voice auto-play preference from backend
            if (userData.voice_autoplay !== undefined) {
              setVoiceAutoPlay(userData.voice_autoplay);
              localStorage.setItem("swavalambi_voice_autoplay", userData.voice_autoplay.toString());
            } else {
              // Fallback to localStorage or default
              const storedVoiceAutoPlay = localStorage.getItem("swavalambi_voice_autoplay");
              if (storedVoiceAutoPlay !== null) {
                setVoiceAutoPlay(storedVoiceAutoPlay === "true");
              } else {
                // First time - enable by default
                setVoiceAutoPlay(true);
                localStorage.setItem("swavalambi_voice_autoplay", "true");
              }
            }
            
            // Trigger chat history load after preferences are loaded
            setIsLoadingHistory(false);
            return;
          }
        } catch (error) {
          console.error("Failed to load preferences from backend:", error);
        }
      }
      
      // Fallback: Load from localStorage only
      const storedLanguage = localStorage.getItem("swavalambi_language");
      if (storedLanguage) {
        setSelectedLanguage(storedLanguage);
      } else {
        setShowLanguageModal(true);
      }
      
      const storedVoiceAutoPlay = localStorage.getItem("swavalambi_voice_autoplay");
      if (storedVoiceAutoPlay !== null) {
        setVoiceAutoPlay(storedVoiceAutoPlay === "true");
      } else {
        setVoiceAutoPlay(true);
        localStorage.setItem("swavalambi_voice_autoplay", "true");
      }
      
      // Trigger chat history load after preferences are loaded
      setIsLoadingHistory(false);
    };
    
    initializePreferences();
  }, []);

  // Toggle voice auto-play
  const toggleVoiceAutoPlay = () => {
    const newValue = !voiceAutoPlay;
    setVoiceAutoPlay(newValue);
    localStorage.setItem("swavalambi_voice_autoplay", newValue.toString());
    
    // Save voice preference to backend
    const userId = localStorage.getItem("swavalambi_user_id");
    if (userId) {
      fetch(`${API_BASE}/users/${userId}/preferences?voice_autoplay=${newValue}`, {
        method: "PUT",
      }).catch(err => console.error("Failed to save voice preference:", err));
    }
  };

  // Close language selector when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (showLanguageSelector) {
        const target = event.target as HTMLElement;
        if (!target.closest('.language-selector-container')) {
          setShowLanguageSelector(false);
        }
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [showLanguageSelector]);

  const handleLanguageSelect = (languageCode: string) => {
    setSelectedLanguage(languageCode);
    localStorage.setItem("swavalambi_language", languageCode);
    setShowLanguageModal(false);
    setShowLanguageSelector(false);
    
    // Save language preference to backend
    const userId = localStorage.getItem("swavalambi_user_id");
    if (userId) {
      fetch(`${API_BASE}/users/${userId}/preferences?language=${languageCode}`, {
        method: "PUT",
      }).catch(err => console.error("Failed to save language preference:", err));
    }
    
    // After language selection, show greeting in selected language
    const storedName = localStorage.getItem("swavalambi_name") || "";
    const userName = storedName && !/^\+?\d{7,}$/.test(storedName.trim()) ? storedName : "";
    const welcomeMessage = getGreeting(languageCode, userName);
    
    // Show greeting if messages are empty (first time OR reassessment)
    if (messages.length === 0) {
      const greetingMessageId = "msg-1";
      setMessages([{ id: greetingMessageId, role: "assistant", content: welcomeMessage }]);
      
      // Save greeting to chat history in DynamoDB
      if (userId && !hasSavedInitialGreetingRef.current) {
        hasSavedInitialGreetingRef.current = true;
        const initialChat = [{ role: "assistant", content: welcomeMessage }];
        fetch(`${API_BASE}/users/${userId}/chat-history`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ chat_history: initialChat })
        }).catch(err => console.error("Failed to save greeting to chat history:", err));
      }
      
      // Auto-play greeting if voice is enabled (only once)
      if (voiceAutoPlay && !hasPlayedGreetingRef.current) {
        hasPlayedGreetingRef.current = true;
        // Small delay to ensure message is rendered
        setTimeout(() => {
          playMessage(greetingMessageId, welcomeMessage);
        }, 500);
      }
    }
  };

  const getCurrentLanguage = () => {
    return languages.find(lang => lang.code === selectedLanguage) || languages[0];
  };

  // Load chat history on mount and when returning to this page
  useEffect(() => {
    let isMounted = true; // Prevent duplicate loading in React Strict Mode
    
    const loadChatHistory = async () => {
      if (!isMounted) return; // Skip if already unmounted
      
      setIsLoadingHistory(true);
      const userId = localStorage.getItem("swavalambi_user_id");
      const storedName = localStorage.getItem("swavalambi_name") || "";
      const userName = storedName && !/^\+?\d{7,}$/.test(storedName.trim()) ? storedName : "";

      // Get language from localStorage directly
      const currentLanguage = localStorage.getItem("swavalambi_language");
      
      // If no language selected yet, don't show greeting - language modal will appear
      if (!currentLanguage) {
        setIsLoadingHistory(false);
        return;
      }
      
      // Build welcome message in selected language
      const buildWelcome = (name: string) => getGreeting(currentLanguage, name);
      
      // Check if this is a reassessment (explicit flag)
      const isReassessment = sessionStorage.getItem("is_reassessment") === "true";
      const urlParams = new URLSearchParams(window.location.search);
      const hasReassessParam = urlParams.get("reassess") === "true";
      
      if (isReassessment || hasReassessParam) {
        // This is a reassessment - start fresh
        console.log("[INFO] Reassessment detected - starting fresh chat");
        sessionStorage.removeItem("is_reassessment");
        const greetingMessage = buildWelcome(userName);
        setMessages([{ id: "msg-1", role: "assistant", content: greetingMessage }]);
        
        // Save greeting to DynamoDB for reassessment
        if (userId && !hasSavedInitialGreetingRef.current) {
          hasSavedInitialGreetingRef.current = true;
          const initialChat = [{ role: "assistant", content: greetingMessage }];
          fetch(`${API_BASE}/users/${userId}/chat-history`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ chat_history: initialChat })
          }).catch(err => console.error("Failed to save reassessment greeting:", err));
        }
        
        setIsLoadingHistory(false);
        
        // Auto-play greeting if voice is enabled (only once)
        const storedVoiceAutoPlay = localStorage.getItem("swavalambi_voice_autoplay");
        const shouldAutoPlay = storedVoiceAutoPlay === null || storedVoiceAutoPlay === "true";
        if (shouldAutoPlay && !hasPlayedGreetingRef.current) {
          hasPlayedGreetingRef.current = true;
          setTimeout(() => {
            playMessage("msg-1", greetingMessage);
          }, 500);
        }
        return;
      }
      
      if (!userId) {
        const greetingMessage = buildWelcome(userName);
        setMessages([{ id: "msg-1", role: "assistant", content: greetingMessage }]);
        setIsLoadingHistory(false);
        
        // Auto-play greeting if voice is enabled (only once)
        const storedVoiceAutoPlay = localStorage.getItem("swavalambi_voice_autoplay");
        const shouldAutoPlay = storedVoiceAutoPlay === null || storedVoiceAutoPlay === "true";
        if (shouldAutoPlay && !hasPlayedGreetingRef.current) {
          hasPlayedGreetingRef.current = true;
          setTimeout(() => {
            playMessage("msg-1", greetingMessage);
          }, 500);
        }
        return;
      }

      try {
        const res = await fetch(`${API_BASE}/users/${userId}/chat-history`);
        if (res.ok) {
          const data = await res.json();
          if (data.chat_history && data.chat_history.length > 0) {
            const loadedMessages: Message[] = data.chat_history.map((msg: any, idx: number) => ({
              id: `loaded-${idx}`,
              role: msg.role,
              content: msg.content || "", // Ensure content is never undefined
              imagePreviewUrl: msg.imagePreviewUrl,
            }));
            setMessages(loadedMessages);
            console.log(`[INFO] Loaded ${loadedMessages.length} messages from history`);
            
            // Scroll to bottom after messages are loaded
            setTimeout(() => {
              messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
            }, 100);
          } else {
            // No chat history - show greeting and auto-play (only once)
            const greetingMessage = buildWelcome(userName);
            setMessages([{ id: "msg-1", role: "assistant", content: greetingMessage }]);
            
            // Auto-play greeting if voice is enabled
            const storedVoiceAutoPlay = localStorage.getItem("swavalambi_voice_autoplay");
            const shouldAutoPlay = storedVoiceAutoPlay === null || storedVoiceAutoPlay === "true";
            if (shouldAutoPlay && !hasPlayedGreetingRef.current) {
              hasPlayedGreetingRef.current = true;
              setTimeout(() => {
                playMessage("msg-1", greetingMessage);
              }, 500);
            }
          }
        } else {
          // Error loading - show greeting and auto-play (only once)
          const greetingMessage = buildWelcome(userName);
          setMessages([{ id: "msg-1", role: "assistant", content: greetingMessage }]);
          
          // Auto-play greeting if voice is enabled
          const storedVoiceAutoPlay = localStorage.getItem("swavalambi_voice_autoplay");
          const shouldAutoPlay = storedVoiceAutoPlay === null || storedVoiceAutoPlay === "true";
          if (shouldAutoPlay && !hasPlayedGreetingRef.current) {
            hasPlayedGreetingRef.current = true;
            setTimeout(() => {
              playMessage("msg-1", greetingMessage);
            }, 500);
          }
        }
      } catch (error) {
        console.error("Failed to load chat history:", error);
        const greetingMessage = buildWelcome(userName);
        setMessages([{ id: "msg-1", role: "assistant", content: greetingMessage }]);
        
        // Auto-play greeting if voice is enabled (only once)
        const storedVoiceAutoPlay = localStorage.getItem("swavalambi_voice_autoplay");
        const shouldAutoPlay = storedVoiceAutoPlay === null || storedVoiceAutoPlay === "true";
        if (shouldAutoPlay && !hasPlayedGreetingRef.current) {
          hasPlayedGreetingRef.current = true;
          setTimeout(() => {
            playMessage("msg-1", greetingMessage);
          }, 500);
        }
      } finally {
        setIsLoadingHistory(false);
      }
    };

    loadChatHistory();
    
    return () => {
      isMounted = false; // Cleanup flag on unmount
    };
  }, [location.pathname]); // Only reload when navigating back, not on language change

  useEffect(() => {
    // Scroll to bottom when messages change, with a small delay to ensure rendering is complete
    if (!isLoadingHistory) {
      setTimeout(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
      }, 50);
    }
  }, [messages, isLoadingHistory]);

  // Cleanup audio on component unmount
  useEffect(() => {
    return () => {
      if (currentAudio) {
        currentAudio.pause();
        currentAudio.currentTime = 0;
      }
    };
  }, [currentAudio]);

  // Playback functions
  const playMessage = async (messageId: string, text: string) => {
    // Stop any currently playing audio
    if (currentAudio) {
      currentAudio.pause();
      currentAudio.currentTime = 0;
    }

    setIsLoadingAudio(messageId);

    try {
      const response = await fetch(`${API_BASE}/voice/synthesize`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text,
          language: selectedLanguage,
        }),
      });

      if (!response.ok) throw new Error("TTS API failed");

      const data = await response.json();
      const audio = new Audio(
        `data:audio/${data.audio_format};base64,${data.audio_base64}`
      );

      // CRITICAL FIX: Set playback rate to 1.0 (normal speed)
      audio.playbackRate = 1.0;

      audio.onended = () => {
        setPlayingMessageId(null);
        setCurrentAudio(null);
      };

      audio.onerror = (e) => {
        console.error("Audio playback failed:", e);
        setPlayingMessageId(null);
        setCurrentAudio(null);
        setIsLoadingAudio(null);
      };

      await audio.play();
      setCurrentAudio(audio);
      setPlayingMessageId(messageId);
    } catch (error) {
      console.error("TTS error:", error);
      alert("Unable to play audio. Please try again.");
    } finally {
      setIsLoadingAudio(null);
    }
  };

  const stopMessage = () => {
    if (currentAudio) {
      currentAudio.pause();
      currentAudio.currentTime = 0;
      setCurrentAudio(null);
    }
    setPlayingMessageId(null);
  };

  // Start redirect countdown
  const startRedirectCountdown = (path: string) => {
    setRedirectPath(path);
    setRedirectCountdown(5);
    
    // Give user 5 seconds to read the final message before showing modal
    setTimeout(() => {
      setShowRedirectModal(true);

      // Clear any existing timer
      if (redirectTimerRef.current) {
        clearInterval(redirectTimerRef.current);
      }

      // Start countdown
      let count = 5;
      redirectTimerRef.current = setInterval(() => {
        count--;
        setRedirectCountdown(count);
        
        if (count <= 0) {
          if (redirectTimerRef.current) {
            clearInterval(redirectTimerRef.current);
          }
          navigate(path);
        }
      }, 1000);
    }, 5000); // 5 second delay before showing modal
  };

  // Cancel redirect
  const cancelRedirect = () => {
    if (redirectTimerRef.current) {
      clearInterval(redirectTimerRef.current);
      redirectTimerRef.current = null;
    }
    setShowRedirectModal(false);
  };

  // Cleanup timer on unmount
  useEffect(() => {
    return () => {
      if (redirectTimerRef.current) {
        clearInterval(redirectTimerRef.current);
      }
    };
  }, []);

  // Detect intent from user message immediately (don't wait for backend final JSON)
  const detectAndCacheIntent = (msg: string) => {
    const lower = msg.toLowerCase();
    if (lower.includes("loan") || lower.includes("business") || lower.includes("scheme")) {
      localStorage.setItem("swavalambi_intent", "loan");
    } else if (lower.includes("upskill") || lower.includes("learn") || lower.includes("training") || lower.includes("improve")) {
      localStorage.setItem("swavalambi_intent", "upskill");
    } else if (lower.includes("job") || lower.includes("employment") || lower.includes("work")) {
      localStorage.setItem("swavalambi_intent", "job");
    }
  };

  const handleClearChat = async () => {
    try {
      const userId = localStorage.getItem("swavalambi_user_id");
      
      // Clear chat history in backend if user is logged in
      if (userId) {
        await fetch(`${API_BASE}/users/${userId}/chat-history`, {
          method: "DELETE",
        });
      }
      
      // Clear local messages with multilingual greeting
      const storedName = localStorage.getItem("swavalambi_name") || "";
      const userName = storedName && !/^\+?\d{7,}$/.test(storedName.trim()) ? storedName : "";
      const welcomeMessage = getGreeting(selectedLanguage, userName);
      
      setMessages([{ id: "msg-1", role: "assistant", content: welcomeMessage }]);
      
      // Clear session to start fresh
      clearSession();
      
      // Close modal
      setShowClearChatModal(false);
      
    } catch (error) {
      console.error("Failed to clear chat history:", error);
      alert("Failed to clear chat history. Please try again.");
    }
  };

  const handleSendMessage = async () => {
    if (!input.trim() || isLoading) return;

    // Early intent detection — save before backend responds
    detectAndCacheIntent(input);

    const userMsg: Message = {
      id: Date.now().toString(),
      role: "user",
      content: input,
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setIsLoading(true);

    try {
      const userId = localStorage.getItem("swavalambi_user_id");
      const userName = localStorage.getItem("swavalambi_name") || "";
      
      const payload: any = { session_id: sessionId, message: input };
      if (userId) payload.user_id = userId;
      if (userName && !/^\+?\d{7,}$/.test(userName.trim())) payload.user_name = userName;

      // Check if streaming is enabled (you can add this to env or make it configurable)
      const enableStreaming = import.meta.env.VITE_ENABLE_STREAMING === "true";
      
      if (enableStreaming) {
        // Streaming mode using SSE
        await handleStreamingResponse(payload);
      } else {
        // Non-streaming mode (original)
        await handleNonStreamingResponse(payload);
      }
    } catch (error) {
      console.error("Chat error:", error);
      setMessages((prev) => [
        ...prev,
        {
          id: (Date.now() + 1).toString(),
          role: "assistant",
          content:
            "Sorry, I am having trouble connecting to the AI. Please ensure the backend server is running on port 8000.",
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleNonStreamingResponse = async (payload: any) => {
    // Original non-streaming implementation
    const assistantMessageId = (Date.now() + 1).toString();

    // Show inline loading dots immediately (same UX as streaming)
    setMessages((prev) => [
      ...prev,
      {
        id: assistantMessageId,
        role: "assistant",
        content: "...",
        isReadyForPhoto: false,
      },
    ]);
    setIsLoading(false); // Global loading no longer needed — inline dots handle it

    const res = await fetch(`${API_BASE}/chat/chat-profile`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!res.ok) throw new Error(`API error: ${res.status}`);
    const data = await res.json();

    setMessages((prev) =>
      prev.map((msg) =>
        msg.id === assistantMessageId
          ? {
              ...msg,
              content: data.response,
              isReadyForPhoto: data.is_ready_for_photo,
            }
          : msg
      )
    );

    // Auto-play voice if enabled
    if (voiceAutoPlay && data.response) {
      playMessage(assistantMessageId, data.response);
    }

    // Cache extracted profile fields
    cacheProfileData(data);

    if (data.is_complete) {
      const userIntent = data.intent_extracted || localStorage.getItem("swavalambi_intent");
      const path = userIntent === "upskill" ? "/upskill" : userIntent === "job" ? "/jobs" : "/home";
      startRedirectCountdown(path);
    }
  };

  const handleStreamingResponse = async (payload: any) => {
    // Streaming implementation using SSE
    const assistantMessageId = (Date.now() + 1).toString();
    let streamedContent = "";
    
    console.log("[DEBUG] Creating assistant message with ID:", assistantMessageId);
    
    // Add assistant message with loading indicator that will be updated as chunks arrive
    setMessages((prev) => [
      ...prev,
      {
        id: assistantMessageId,
        role: "assistant",
        content: "...", // Show loading indicator initially
        isReadyForPhoto: false,
      },
    ]);

    const response = await fetch(`${API_BASE}/chat/chat-profile-stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!response.ok) throw new Error(`API error: ${response.status}`);
    if (!response.body) throw new Error("No response body");

    const reader = response.body.getReader();
    const decoder = new TextDecoder();

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split("\n");

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            const jsonStr = line.slice(6);
            try {
              const data = JSON.parse(jsonStr);

              if (data.error) {
                throw new Error(data.error);
              }

              if (data.chunk) {
                // Append chunk to streamed content
                streamedContent += data.chunk;
                
                console.log("[DEBUG] Received chunk, total length:", streamedContent.length);
                
                // Update message with accumulated content
                setMessages((prev) =>
                  prev.map((msg) =>
                    msg.id === assistantMessageId
                      ? { ...msg, content: streamedContent }
                      : msg
                  )
                );
              }

              if (data.done) {
                console.log("[DEBUG] Stream done, final content length:", streamedContent.length);
                console.log("[DEBUG] Current messages count before update:", messages.length);
                
                // Stream complete - update with final metadata
                // If streamedContent is still empty, show error
                const finalContent = streamedContent || "Sorry, I received an empty response. Please try again.";
                
                setMessages((prev) => {
                  console.log("[DEBUG] Messages in state before final update:", prev.length);
                  const updated = prev.map((msg) =>
                    msg.id === assistantMessageId
                      ? {
                          ...msg,
                          content: finalContent,
                          isReadyForPhoto: data.is_ready_for_photo || false,
                        }
                      : msg
                  );
                  console.log("[DEBUG] Messages after final update:", updated.length);
                  return updated;
                });

                // Auto-play voice if enabled (play complete response)
                if (voiceAutoPlay && streamedContent) {
                  playMessage(assistantMessageId, streamedContent);
                }

                // Cache extracted profile fields
                cacheProfileData(data);

                if (data.is_complete) {
                  const userIntent = data.intent_extracted || localStorage.getItem("swavalambi_intent");
                  const path = userIntent === "upskill" ? "/upskill" : userIntent === "job" ? "/jobs" : "/home";
                  startRedirectCountdown(path);
                }
              }
            } catch (e) {
              console.error("Failed to parse SSE data:", e);
            }
          }
        }
      }
    } finally {
      reader.releaseLock();
    }
  };

  const cacheProfileData = (data: any) => {
    // Helper function to cache extracted profile fields
    if (data.intent_extracted) {
      localStorage.setItem("swavalambi_intent", data.intent_extracted);
    }
    if (data.profession_skill_extracted) {
      localStorage.setItem("swavalambi_skill", data.profession_skill_extracted);
    }
    if (data.theory_score_extracted) {
      localStorage.setItem("swavalambi_theory_score", data.theory_score_extracted.toString());
    }
    if (data.gender_extracted) {
      localStorage.setItem("swavalambi_gender", data.gender_extracted.toLowerCase());
    }
    if (data.location_extracted) {
      localStorage.setItem("swavalambi_location", data.location_extracted);
    }
  };

  const handleSendMessageOld = async () => {
    if (!input.trim() || isLoading) return;

    // Early intent detection — save before backend responds
    detectAndCacheIntent(input);

    const userMsg: Message = {
      id: Date.now().toString(),
      role: "user",
      content: input,
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setIsLoading(true);

    try {
      const userId = localStorage.getItem("swavalambi_user_id");
      const userName = localStorage.getItem("swavalambi_name") || "";
      
      const payload: any = { session_id: sessionId, message: input };
      if (userId) payload.user_id = userId;
      if (userName && !/^\+?\d{7,}$/.test(userName.trim())) payload.user_name = userName;

      // Real call to FastAPI backend -> ProfilingAgent -> Bedrock/Anthropic
      const res = await fetch(`${API_BASE}/chat/chat-profile`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) throw new Error(`API error: ${res.status}`);
      const data = await res.json();

      const assistantMessageId = (Date.now() + 1).toString();
      setMessages((prev) => [
        ...prev,
        {
          id: assistantMessageId,
          role: "assistant",
          content: data.response,
          isReadyForPhoto: data.is_ready_for_photo,
        },
      ]);

      // Auto-play voice if enabled
      if (voiceAutoPlay && data.response) {
        playMessage(assistantMessageId, data.response);
      }

      // Cache extracted profile fields for recommendations
      if (data.intent_extracted) {
        localStorage.setItem("swavalambi_intent", data.intent_extracted);
      }
      if (data.profession_skill_extracted) {
        localStorage.setItem("swavalambi_skill", data.profession_skill_extracted);
      }
      if (data.theory_score_extracted) {
        localStorage.setItem("swavalambi_theory_score", data.theory_score_extracted.toString());
      }
      if (data.gender_extracted) {
        localStorage.setItem("swavalambi_gender", data.gender_extracted.toLowerCase());
      }
      if (data.location_extracted) {
        localStorage.setItem("swavalambi_location", data.location_extracted);
      }
      if (data.is_complete) {
        // Start redirect countdown instead of immediate redirect
        const userIntent = data.intent_extracted || localStorage.getItem("swavalambi_intent");
        const path = userIntent === "upskill" ? "/upskill" : userIntent === "job" ? "/jobs" : "/home";
        startRedirectCountdown(path);
      }
    } catch (e) {
      console.error(e);
      setMessages((prev) => [
        ...prev,
        {
          id: (Date.now() + 1).toString(),
          role: "assistant",
          content:
            "Sorry, I am having trouble connecting to the AI. Please ensure the backend server is running on port 8000.",
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const url = URL.createObjectURL(file);
    setMessages((prev) => [
      ...prev,
      {
        id: Date.now().toString(),
        role: "user",
        content: `Uploaded work sample: ${file.name}`,
        imagePreviewUrl: url,
      },
    ]);

    setIsLoading(true);
    try {
      // Real call to FastAPI backend -> VisionAgent -> Bedrock Vision
      const formData = new FormData();
      formData.append("session_id", sessionId);
      formData.append("photo", file);
      // Pass user identity so backend can persist assessment to DynamoDB
      const userId = localStorage.getItem("swavalambi_user_id") || "";
      const skill  = localStorage.getItem("swavalambi_skill") || "";
      const intent = localStorage.getItem("swavalambi_intent") || "job";
      const theoryScore = localStorage.getItem("swavalambi_theory_score") || "";
      if (userId) formData.append("user_id", userId);
      if (skill)  formData.append("skill", skill);
      formData.append("intent", intent);
      if (theoryScore) formData.append("theory_score", theoryScore);

      const res = await fetch(`${API_BASE}/vision/analyze-vision`, {
        method: "POST",
        body: formData,
      });

      if (!res.ok) throw new Error(`Vision API error: ${res.status}`);
      const result = await res.json();

      localStorage.setItem(
        "swavalambi_skill_rating",
        result.skill_rating.toString(),
      );
      // Keep intent from the chat agent if already set
      if (!localStorage.getItem("swavalambi_intent")) {
        localStorage.setItem("swavalambi_intent", "job");
      }

      const assistantMessageId = (Date.now() + 1).toString();
      setMessages((prev) => [
        ...prev,
        {
          id: assistantMessageId,
          role: "assistant",
          content: result.feedback,  // Just use the feedback from backend (already in user's language)
        },
      ]);

      // Auto-play feedback if voice is enabled
      if (voiceAutoPlay) {
        // Small delay to ensure message is rendered
        setTimeout(() => {
          playMessage(assistantMessageId, result.feedback);
        }, 500);
      }

      // Start redirect countdown instead of immediate redirect
      const userIntent = localStorage.getItem("swavalambi_intent");
      const path = userIntent === "upskill" ? "/upskill" : userIntent === "job" ? "/jobs" : "/home";
      startRedirectCountdown(path);
    } catch (e) {

      console.error(e);
      setMessages((prev) => [
        ...prev,
        {
          id: (Date.now() + 1).toString(),
          role: "assistant",
          content:
            "Sorry, I could not analyze the image. Please ensure the backend is running and try again.",
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSkipAssessment = () => {
    // Escape hatch: Zero rating sets them to upskilling focus
    localStorage.setItem("swavalambi_skill_rating", "0");
    localStorage.setItem("swavalambi_intent", "upskill");
    navigate("/upskill");
  };

  // Voice recording functions
  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      const audioChunks: Blob[] = [];

      recorder.ondataavailable = (event) => {
        audioChunks.push(event.data);
      };

      recorder.onstop = async () => {
        const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
        await sendVoiceMessage(audioBlob);
        stream.getTracks().forEach(track => track.stop());
      };

      recorder.start();
      setMediaRecorder(recorder);
      setIsRecording(true);
    } catch (error) {
      console.error("Microphone access denied:", error);
      alert("Please allow microphone access to use voice input");
    }
  };

  const stopRecording = () => {
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
      mediaRecorder.stop();
      setIsRecording(false);
    }
  };

  const sendVoiceMessage = async (audioBlob: Blob) => {
    setIsLoading(true);
    
    // Check if streaming is enabled
    const enableStreaming = import.meta.env.VITE_ENABLE_STREAMING === "true";
    
    if (enableStreaming) {
      await sendVoiceMessageStreaming(audioBlob);
    } else {
      await sendVoiceMessageNonStreaming(audioBlob);
    }
  };

  const sendVoiceMessageNonStreaming = async (audioBlob: Blob) => {
    try {
      const formData = new FormData();
      formData.append('audio', audioBlob, 'recording.webm');
      formData.append('session_id', sessionId);
      formData.append('language', selectedLanguage);
      
      const userId = localStorage.getItem("swavalambi_user_id");
      if (userId) formData.append('user_id', userId);

      const res = await fetch(`${API_BASE}/voice/chat`, {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) throw new Error(`Voice API error: ${res.status}`);
      const data = await res.json();

      // Add user message
      setMessages((prev) => [
        ...prev,
        {
          id: Date.now().toString(),
          role: "user",
          content: data.transcribed_text,
        },
      ]);

      // Add assistant response
      const assistantMessageId = (Date.now() + 1).toString();
      setMessages((prev) => [
        ...prev,
        {
          id: assistantMessageId,
          role: "assistant",
          content: data.response_text,
          isReadyForPhoto: data.is_ready_for_photo,
        },
      ]);

      // Play audio response
      if (data.audio_base64) {
        playAudio(data.audio_base64, data.audio_format, assistantMessageId);
      }

      // Cache extracted data
      cacheProfileData(data);
      
      if (data.is_complete) {
        const userIntent = data.intent_extracted || localStorage.getItem("swavalambi_intent");
        const path = userIntent === "upskill" ? "/upskill" : userIntent === "job" ? "/jobs" : "/home";
        startRedirectCountdown(path);
      }
    } catch (error) {
      console.error("Voice chat error:", error);
      setMessages((prev) => [
        ...prev,
        {
          id: (Date.now() + 1).toString(),
          role: "assistant",
          content: "Sorry, I couldn't process your voice message. Please try again or type your message.",
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const sendVoiceMessageStreaming = async (audioBlob: Blob) => {
    // Generate unique IDs upfront to prevent collisions
    const userMsgId = `user-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    const assistantMsgId = `assistant-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    
    try {
      const formData = new FormData();
      formData.append('audio', audioBlob, 'recording.webm');
      formData.append('session_id', sessionId);
      formData.append('language', selectedLanguage);
      
      const userId = localStorage.getItem("swavalambi_user_id");
      if (userId) formData.append('user_id', userId);

      const response = await fetch(`${API_BASE}/voice/chat-stream`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) throw new Error(`Voice API error: ${response.status}`);
      if (!response.body) throw new Error("No response body");

      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      let userMessageAdded = false;
      let assistantMessageAdded = false;
      let fullText = "";
      let buffer = ""; // Buffer for incomplete JSON chunks

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        // Add new data to buffer
        buffer += decoder.decode(value, { stream: true });
        
        // Split by double newline (SSE message separator)
        const sseMessages = buffer.split('\n\n');
        
        // Keep the last incomplete message in buffer
        buffer = sseMessages.pop() || "";

        for (const sseMessage of sseMessages) {
          const lines = sseMessage.split("\n");
          
          for (const line of lines) {
            if (line.startsWith("data: ")) {
              const jsonStr = line.slice(6);
              try {
                const data = JSON.parse(jsonStr);

                if (data.type === "transcription") {
                  // Add user message once
                  if (!userMessageAdded) {
                    setMessages((prev) => [
                      ...prev,
                      {
                        id: userMsgId,
                        role: "user",
                        content: data.text,
                      },
                    ]);
                    userMessageAdded = true;
                  }
                  
                  // Create assistant message with loading indicator once
                  if (!assistantMessageAdded) {
                    setMessages((prev) => [
                      ...prev,
                      {
                        id: assistantMsgId,
                        role: "assistant",
                        content: "...", // Loading indicator (will be replaced by first chunk)
                      },
                    ]);
                    assistantMessageAdded = true;
                    
                    // Turn off global loading since we have message-level loading
                    setIsLoading(false);
                  }
                } else if (data.type === "text_chunk") {
                  // STREAMING TEXT: Update message with each chunk as it arrives
                  if (data.text) {
                    fullText += data.text;
                    
                    setMessages((prev) =>
                      prev.map((msg) =>
                        msg.id === assistantMsgId
                          ? { ...msg, content: fullText }
                          : msg
                      )
                    );
                  }
                } else if (data.type === "audio_complete") {
                  // Complete audio received - play it if voice is enabled
                  if (voiceAutoPlay && data.audio_base64) {
                    try {
                      const audio = new Audio(
                        `data:audio/${data.audio_format};base64,${data.audio_base64}`
                      );
                      audio.playbackRate = 1.0;
                      
                      audio.onended = () => {
                        setPlayingMessageId(null);
                        setCurrentAudio(null);
                      };
                      
                      audio.onerror = (e) => {
                        console.error("Audio playback failed:", e);
                        setPlayingMessageId(null);
                        setCurrentAudio(null);
                      };
                      
                      await audio.play();
                      setCurrentAudio(audio);
                      setPlayingMessageId(assistantMsgId);
                    } catch (error) {
                      console.error("Audio playback failed:", error);
                    }
                  }
                } else if (data.type === "text_complete") {
                  // Fallback: Update message with complete text (in case we missed chunks)
                  if (data.text && data.text !== fullText) {
                    fullText = data.text;
                    setMessages((prev) =>
                      prev.map((msg) =>
                        msg.id === assistantMsgId
                          ? { ...msg, content: fullText }
                          : msg
                      )
                    );
                  }
                } else if (data.type === "complete") {
                  // Update with final metadata
                  if (fullText) {
                    setMessages((prev) =>
                      prev.map((msg) =>
                        msg.id === assistantMsgId
                          ? {
                              ...msg,
                              content: fullText,
                              isReadyForPhoto: data.is_ready_for_photo || false,
                            }
                          : msg
                      )
                    );
                  }

                  // Cache profile data
                  cacheProfileData(data);

                  if (data.is_complete) {
                    const userIntent = data.intent_extracted || localStorage.getItem("swavalambi_intent");
                    const path = userIntent === "upskill" ? "/upskill" : userIntent === "job" ? "/jobs" : "/home";
                    startRedirectCountdown(path);
                  }
                }
              } catch (e) {
                console.error("Failed to parse SSE data:", e);
              }
            }
          }
        }
      }
      
    } catch (error) {
      console.error("Streaming voice chat error:", error);
      
      // Remove the loading "..." message if it exists and replace with error
      setMessages((prev) => {
        const filtered = prev.filter(msg => msg.id !== assistantMsgId);
        return [
          ...filtered,
          {
            id: (Date.now() + 1).toString(),
            role: "assistant",
            content: "Sorry, I couldn't process your voice message. Please try again.",
          },
        ];
      });
    } finally {
      setIsLoading(false);
    }
  };

  const playAudioChunk = (base64Audio: string, format: string) => {
    // Play audio chunk immediately (non-blocking)
    const audio = new Audio(`data:audio/${format};base64,${base64Audio}`);
    
    // CRITICAL FIX: Set playback rate to 1.0 (normal speed)
    audio.playbackRate = 1.0;
    
    audio.play().catch(err => console.error("Audio playback failed:", err));
  };

  const playAudioChunkSequential = (base64Audio: string, format: string): Promise<void> => {
    // Play audio chunk and wait for it to finish
    return new Promise((resolve) => {
      const audio = new Audio(`data:audio/${format};base64,${base64Audio}`);
      audio.onended = () => resolve();
      audio.onerror = () => resolve(); // Continue even if playback fails
      audio.play().catch(err => {
        console.error("Audio playback failed:", err);
        resolve();
      });
    });
  };

  const sendVoiceMessageOld = async (audioBlob: Blob) => {
    setIsLoading(true);
    
    try {
      const formData = new FormData();
      formData.append('audio', audioBlob, 'recording.webm');
      formData.append('session_id', sessionId);
      formData.append('language', selectedLanguage);
      
      const userId = localStorage.getItem("swavalambi_user_id");
      if (userId) formData.append('user_id', userId);

      const res = await fetch(`${API_BASE}/voice/chat`, {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) throw new Error(`Voice API error: ${res.status}`);
      const data = await res.json();

      // Add user message
      setMessages((prev) => [
        ...prev,
        {
          id: Date.now().toString(),
          role: "user",
          content: data.transcribed_text,
        },
      ]);

      // Add assistant response
      const assistantMessageId = (Date.now() + 1).toString();
      setMessages((prev) => [
        ...prev,
        {
          id: assistantMessageId,
          role: "assistant",
          content: data.response_text, // Changed from localized_response to response_text
          isReadyForPhoto: data.is_ready_for_photo,
        },
      ]);

      // Play audio response with message ID for playback button sync
      if (data.audio_base64) {
        playAudio(data.audio_base64, data.audio_format, assistantMessageId);
      }

      // Cache extracted data
      if (data.intent_extracted) {
        localStorage.setItem("swavalambi_intent", data.intent_extracted);
      }
      if (data.profession_skill_extracted) {
        localStorage.setItem("swavalambi_skill", data.profession_skill_extracted);
      }
      if (data.theory_score_extracted) {
        localStorage.setItem("swavalambi_theory_score", data.theory_score_extracted.toString());
      }
      if (data.gender_extracted) {
        localStorage.setItem("swavalambi_gender", data.gender_extracted.toLowerCase());
      }
      
      if (data.is_complete) {
        // Start redirect countdown instead of immediate redirect
        const userIntent = data.intent_extracted || localStorage.getItem("swavalambi_intent");
        const path = userIntent === "upskill" ? "/upskill" : userIntent === "job" ? "/jobs" : "/home";
        startRedirectCountdown(path);
      }
    } catch (error) {
      console.error("Voice chat error:", error);
      setMessages((prev) => [
        ...prev,
        {
          id: (Date.now() + 1).toString(),
          role: "assistant",
          content: "Sorry, I couldn't process your voice message. Please try again or type your message.",
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const playAudio = (base64Audio: string, format: string, messageId?: string) => {
    // Stop any currently playing audio
    if (currentAudio) {
      currentAudio.pause();
      currentAudio.currentTime = 0;
    }

    const audio = new Audio(`data:audio/${format};base64,${base64Audio}`);
    
    // CRITICAL FIX: Set playback rate to 1.0 (normal speed)
    // This prevents the audio from playing too fast
    audio.playbackRate = 1.0;
    
    // Set up event handlers
    audio.onended = () => {
      setPlayingMessageId(null);
      setCurrentAudio(null);
    };
    
    audio.onerror = (e) => {
      console.error("Audio playback failed:", e);
      setPlayingMessageId(null);
      setCurrentAudio(null);
    };
    
    // Play and update state
    audio.play().catch(err => {
      console.error("Audio playback failed:", err);
      setPlayingMessageId(null);
      setCurrentAudio(null);
    });
    
    setCurrentAudio(audio);
    if (messageId) {
      setPlayingMessageId(messageId);
    }
  };

  return (
    <div className="bg-background-light text-slate-900 min-h-screen flex flex-col">
      <header className="sticky top-0 z-10 bg-background-light/80 backdrop-blur-md border-b border-primary/10">
        <div className="flex items-center justify-between p-4 max-w-lg mx-auto w-full">
          <Link
            to="/home"
            className="p-2 hover:bg-primary/10 rounded-full transition-colors"
          >
            <ArrowLeft className="text-slate-700" />
          </Link>
          <div className="flex flex-col items-center">
            <h1 className="text-lg font-bold leading-tight">AI Assistant</h1>
            <div className="flex items-center gap-1">
              <span className="w-2 h-2 bg-green-500 rounded-full"></span>
              <span className="text-[10px] font-medium uppercase tracking-wider text-slate-500">
                Online
              </span>
            </div>
          </div>
          <div className="flex items-center gap-1 language-selector-container">
            <button 
              onClick={toggleVoiceAutoPlay}
              className={`p-2 hover:bg-primary/10 rounded-full transition-colors ${
                voiceAutoPlay ? "bg-primary/10" : ""
              }`}
              title={voiceAutoPlay ? "Voice auto-play enabled" : "Voice auto-play disabled"}
            >
              {voiceAutoPlay ? (
                <Volume2 className="text-primary" size={20} />
              ) : (
                <VolumeX className="text-slate-400" size={20} />
              )}
            </button>
            <button 
              onClick={() => setShowLanguageSelector(!showLanguageSelector)}
              className="p-2 hover:bg-primary/10 rounded-full transition-colors relative"
              title={`Language: ${getCurrentLanguage().nativeName}`}
            >
              <Globe className="text-slate-700" size={20} />
              <span className="absolute -bottom-1 -right-1 text-xs">
                {getCurrentLanguage().flag}
              </span>
            </button>
            <button 
              onClick={() => setShowClearChatModal(true)}
              className="p-2 hover:bg-primary/10 rounded-full transition-colors"
              title="Clear chat history"
            >
              <History className="text-slate-700" />
            </button>
          </div>
        </div>

        {/* Language selector dropdown */}
        {showLanguageSelector && (
          <div className="absolute right-4 top-16 bg-white rounded-xl shadow-2xl border border-slate-200 p-2 w-64 max-h-96 overflow-y-auto z-50 language-selector-container">
            <div className="text-xs font-semibold text-slate-500 px-3 py-2 uppercase tracking-wide">
              Select Language
            </div>
            {languages.map((lang) => (
              <button
                key={lang.code}
                onClick={() => handleLanguageSelect(lang.code)}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-left transition-colors ${
                  selectedLanguage === lang.code
                    ? "bg-primary/10 text-primary font-semibold"
                    : "hover:bg-slate-50 text-slate-700"
                }`}
              >
                <span className="text-2xl">{lang.flag}</span>
                <div className="flex-1">
                  <div className="text-sm font-medium">{lang.name}</div>
                  <div className="text-xs text-slate-500">{lang.nativeName}</div>
                </div>
                {selectedLanguage === lang.code && (
                  <div className="w-2 h-2 bg-primary rounded-full"></div>
                )}
              </button>
            ))}
          </div>
        )}
      </header>

      <main className="flex-1 overflow-y-auto p-4 space-y-6 mx-auto w-full pb-80">
        {/* Skip Header */}
        <div className="flex justify-center mb-4">
          <button
            onClick={handleSkipAssessment}
            className="flex items-center gap-2 px-4 py-2 bg-slate-100 text-slate-600 rounded-full text-xs font-semibold hover:bg-slate-200 transition-colors shadow-sm border border-slate-200"
          >
            <SkipForward size={14} /> Skip Assessment For Now
          </button>
        </div>

        {/* Loading history indicator */}
        {isLoadingHistory && (
          <div className="flex items-center justify-center gap-2 text-slate-500 text-sm">
            <div className="w-4 h-4 border-2 border-primary border-t-transparent rounded-full animate-spin"></div>
            Loading conversation history...
          </div>
        )}

        {(() => {
          const lastAssistantIdx = messages.map((m, i) => m.role === "assistant" ? i : -1).filter(i => i !== -1).at(-1) ?? -1;
          return messages.map((msg, msgIdx) => (
          <div
            key={msg.id}
            className={`flex items-start gap-3 ${msg.role === "user" ? "justify-end" : ""}`}
          >
            {msg.role === "assistant" && (
              <div className="w-10 h-10 rounded-full bg-primary flex items-center justify-center text-white shrink-0 shadow-lg shadow-primary/20">
                <Bot className="fill-current" />
              </div>
            )}

            <div
              className={`flex flex-col gap-1 ${msg.role === "user" ? "items-end max-w-[80%]" : "flex-1"}`}
            >
              <p
                className={`text-[11px] font-semibold uppercase ${msg.role === "user" ? "text-slate-400 mr-1" : "text-primary ml-1"}`}
              >
                {msg.role === "user" ? "You" : "Assistant"}
              </p>

              <div className={`flex items-end gap-2 ${msg.role === "user" ? "flex-row-reverse" : ""}`}>
                <div
                  className={`p-4 rounded-xl shadow-sm border ${
                    msg.role === "user"
                      ? "bg-primary text-white rounded-tr-none border-primary"
                      : "bg-white text-slate-900 rounded-tl-none border-slate-100"
                  } ${msg.role === "assistant" ? "max-w-[calc(100%-3rem)]" : ""}`}
                >
                  {msg.imagePreviewUrl && (
                    <div className="relative mb-2">
                      <img
                        src={msg.imagePreviewUrl}
                        alt="Upload preview"
                        className="rounded-lg max-w-full h-40 object-cover"
                      />
                    </div>
                  )}

                  {/* Render markdown for assistant, plain text for user */}
                  {msg.role === "assistant" ? (
                    <div className="space-y-0.5">
                      {msg.content === "..." ? (
                        // Show animated loading dots without text
                        <div className="flex items-center gap-1 py-1">
                          <div className="w-2 h-2 bg-primary/60 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
                          <div className="w-2 h-2 bg-primary/60 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
                          <div className="w-2 h-2 bg-primary/60 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
                        </div>
                      ) : msg.content ? (
                        renderMarkdown(msg.content)
                      ) : (
                        <p className="text-sm text-gray-500">No message content</p>
                      )}
                    </div>
                  ) : (
                    <p className="text-sm leading-relaxed whitespace-pre-wrap">
                      {msg.content || ""}
                    </p>
                  )}

                  {/* Clickable option chips — only on the LATEST assistant message */}
                  {msg.role === "assistant" && msg.content && msgIdx === lastAssistantIdx &&
                    (() => {
                      const opts = extractOptions(msg.content);
                      return opts.length > 0 ? (
                        <div className="mt-3 flex flex-wrap gap-2">
                          {opts.map((opt, i) => (
                            <button
                              key={i}
                              onClick={() => {
                                setInput(opt);
                              }}
                              className="text-xs font-semibold px-3 py-1.5 bg-primary/10 text-primary border border-primary/25 rounded-full hover:bg-primary hover:text-white active:scale-95 transition-all duration-150"
                            >
                              {opt}
                            </button>
                          ))}
                        </div>
                      ) : null;
                    })()}

                  {msg.isReadyForPhoto && (
                    <div className="mt-3">
                      <button
                        onClick={() => fileInputRef.current?.click()}
                        className="flex items-center gap-2 px-4 py-2 bg-primary/10 text-primary border border-primary/20 rounded-lg text-sm font-semibold hover:bg-primary/20 transition-colors w-full justify-center"
                      >
                        <ImageIcon size={16} /> Upload Work Sample
                      </button>
                    </div>
                  )}
                </div>

                {/* Playback Button - Outside message bubble, only for assistant messages */}
                {msg.role === "assistant" && (
                  <div className="flex-shrink-0 mb-1">
                    <PlaybackButton
                      messageId={msg.id}
                      messageText={msg.content}
                      isLoading={isLoadingAudio === msg.id}
                      isPlaying={playingMessageId === msg.id}
                      onPlay={() => playMessage(msg.id, msg.content)}
                      onStop={stopMessage}
                    />
                  </div>
                )}
              </div>
            </div>

            {msg.role === "user" && (
              <div className="w-10 h-10 rounded-full bg-slate-200 flex items-center justify-center shrink-0">
                <User className="text-slate-500" />
              </div>
            )}
          </div>
        ));
        })()}

        {/* Loading dots are shown inline inside each assistant message (content === "...") */}

        <div ref={messagesEndRef} />
      </main>

      <div className="fixed bottom-20 left-1/2 -translate-x-1/2 w-full max-w-[480px] px-4 z-20">
        <div className="bg-white rounded-2xl shadow-2xl border border-slate-100 p-4">
          <div className="flex items-center gap-3">
            <input
              type="file"
              accept="image/*"
              className="hidden"
              ref={fileInputRef}
              onChange={handleFileUpload}
            />
            <button
              onClick={() => fileInputRef.current?.click()}
              className="p-2 text-slate-400 hover:text-primary transition-colors"
              title="Upload Image"
            >
              <ImageIcon />
            </button>
            <div className="flex-1 bg-slate-100 rounded-xl px-4 py-3">
              <input
                className="bg-transparent border-none focus:ring-0 w-full text-sm placeholder:text-slate-500"
                placeholder="Type or ask anything..."
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSendMessage()}
              />
            </div>
            {input.trim() ? (
              <button
                onClick={handleSendMessage}
                className="w-12 h-12 bg-primary text-white rounded-full flex items-center justify-center shadow-lg shadow-primary/30 hover:scale-105 transition-transform"
              >
                <Send className="w-5 h-5 fill-current ml-1" />
              </button>
            ) : isRecording ? (
              <button
                onClick={stopRecording}
                className="w-12 h-12 bg-red-500 text-white rounded-full flex items-center justify-center shadow-lg animate-pulse"
                title="Stop Recording"
              >
                <div className="w-4 h-4 bg-white rounded-sm"></div>
              </button>
            ) : (
              <button
                onClick={startRecording}
                className="w-12 h-12 bg-primary text-white rounded-full flex items-center justify-center shadow-lg shadow-primary/30 hover:scale-105 transition-transform"
                title="Voice Input"
              >
                <Mic className="fill-current" />
              </button>
            )}
          </div>

          <div className="mt-4 flex items-center gap-2 overflow-x-auto no-scrollbar py-1">
            <span className="text-[10px] font-bold text-slate-400 uppercase shrink-0">
              Suggestions:
            </span>
            <button className="text-xs text-slate-600 whitespace-nowrap px-3 py-1 bg-slate-50 rounded-lg border border-slate-200">
              Ask about jobs
            </button>
            <button className="text-xs text-slate-600 whitespace-nowrap px-3 py-1 bg-slate-50 rounded-lg border border-slate-200">
              Learn about loans
            </button>
            <button className="text-xs text-slate-600 whitespace-nowrap px-3 py-1 bg-slate-50 rounded-lg border border-slate-200">
              Skill training
            </button>
          </div>
        </div>
      </div>

      {/* Redirect Countdown Modal */}
      {showRedirectModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl p-6 max-w-sm w-full shadow-2xl">
            <div className="text-center">
              <div className="w-16 h-16 bg-primary/10 rounded-full flex items-center justify-center mx-auto mb-4">
                <span className="text-3xl font-bold text-primary">{redirectCountdown}</span>
              </div>
              <h3 className="text-lg font-bold text-slate-800 mb-2">
                Redirecting to {redirectPath === "/jobs" ? "Jobs" : redirectPath === "/upskill" ? "Upskill" : "Schemes"}
              </h3>
              <p className="text-sm text-slate-600 mb-6">
                Taking you to your personalized dashboard in {redirectCountdown} seconds...
              </p>
              <div className="flex gap-3">
                <button
                  onClick={cancelRedirect}
                  className="flex-1 px-4 py-2 bg-slate-100 text-slate-700 rounded-lg font-semibold hover:bg-slate-200 transition-colors"
                >
                  Stay Here
                </button>
                <button
                  onClick={() => {
                    if (redirectTimerRef.current) {
                      clearInterval(redirectTimerRef.current);
                    }
                    navigate(redirectPath);
                  }}
                  className="flex-1 px-4 py-2 bg-primary text-white rounded-lg font-semibold hover:bg-primary/90 transition-colors"
                >
                  Go Now
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Language Selection Modal (First Time) */}
      {showLanguageModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl p-6 max-w-md w-full shadow-2xl">
            <div className="text-center mb-6">
              <div className="w-16 h-16 bg-primary/10 rounded-full flex items-center justify-center mx-auto mb-4">
                <Languages className="w-8 h-8 text-primary" />
              </div>
              <h3 className="text-xl font-bold text-slate-800 mb-2">
                Choose Your Language
              </h3>
              <p className="text-sm text-slate-600">
                Select your preferred language for voice conversations
              </p>
            </div>
            <div className="space-y-2 max-h-96 overflow-y-auto">
              {languages.map((lang) => (
                <button
                  key={lang.code}
                  onClick={() => handleLanguageSelect(lang.code)}
                  className="w-full flex items-center gap-3 px-4 py-3 rounded-xl text-left transition-all hover:bg-primary/5 hover:scale-[1.02] border-2 border-transparent hover:border-primary/20"
                >
                  <span className="text-3xl">{lang.flag}</span>
                  <div className="flex-1">
                    <div className="text-base font-semibold text-slate-800">{lang.name}</div>
                    <div className="text-sm text-slate-500">{lang.nativeName}</div>
                  </div>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Clear Chat Confirmation Modal */}
      {showClearChatModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl p-6 max-w-sm w-full shadow-2xl">
            <div className="text-center">
              <div className="w-16 h-16 bg-red-50 rounded-full flex items-center justify-center mx-auto mb-4">
                <History className="w-8 h-8 text-red-500" />
              </div>
              <h3 className="text-lg font-bold text-slate-800 mb-2">
                Clear Chat History?
              </h3>
              <p className="text-sm text-slate-600 mb-6">
                This will delete all messages and start a fresh conversation. Your profile data will be preserved.
              </p>
              <div className="flex gap-3">
                <button
                  onClick={() => setShowClearChatModal(false)}
                  className="flex-1 px-4 py-2 bg-slate-100 text-slate-700 rounded-lg font-semibold hover:bg-slate-200 transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={handleClearChat}
                  className="flex-1 px-4 py-2 bg-red-500 text-white rounded-lg font-semibold hover:bg-red-600 transition-colors"
                >
                  Clear Chat
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      <BottomNav />
    </div>
  );
}
