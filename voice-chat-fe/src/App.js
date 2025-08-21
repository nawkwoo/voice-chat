import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Howl } from "howler";

// --- 컴포넌트 전체 스타일 정의 (JavaScript-in-CSS) ---
// 이 스타일 문자열은 컴포넌트가 마운트될 때 <style> 태그로 문서 헤더에 삽입됩니다.
// 현대적인 다크 테마의 채팅 UI를 구성합니다.
const styles = `
  * {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
  }
  
  html, body {
    margin: 0;
    padding: 0;
    width: 100%;
    height: 100%;
    overflow: hidden;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif;
  }
  
  #root {
    width: 100vw;
    height: 100vh;
    margin: 0;
    padding: 0;
  }
  
  @keyframes pulse {
    0% { transform: scale(1); }
    50% { transform: scale(1.05); }
    100% { transform: scale(1); }
  }
  
  .pulse-animation {
    animation: pulse 1.5s ease-in-out infinite;
  }
  
  @keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
  }
  
  .spinner {
    animation: spin 1.5s linear infinite;
  }
  
  .chat-container {
    display: flex;
    width: 100vw;
    height: 100vh;
    background: #1a1a1a;
    position: fixed;
    top: 0;
    left: 0;
  }
  
  .sidebar {
    width: 300px;
    background: linear-gradient(180deg, #2d2d2d, #262626);
    color: white;
    display: flex;
    flex-direction: column;
    border-right: 1px solid #404040;
    box-shadow: 4px 0 15px rgba(0, 0, 0, 0.2);
  }
  
  .sidebar-toggle {
    display: none;
  }
  
  .sidebar-header {
    padding: 20px;
    border-bottom: 1px solid #444;
    background: #333;
  }
  
  .new-chat-btn {
    width: 100%;
    padding: 12px;
    background: linear-gradient(135deg, #4a90e2, #357abd);
    color: white;
    border: none;
    border-radius: 25px;
    cursor: pointer;
    font-size: 14px;
    font-weight: 500;
    transition: all 0.3s ease;
    box-shadow: 0 4px 15px rgba(74, 144, 226, 0.3);
  }
  
  .new-chat-btn:hover {
    background: linear-gradient(135deg, #357abd, #2a5a8a);
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(74, 144, 226, 0.4);
  }
  
  .new-chat-btn:disabled {
    background: #555;
    cursor: not-allowed;
    transform: none;
    box-shadow: none;
  }
  
  .sessions-list {
    flex: 1;
    overflow-y: auto;
    padding: 10px;
  }
  
  .sessions-list::-webkit-scrollbar {
    width: 6px;
  }
  
  .sessions-list::-webkit-scrollbar-track {
    background: #333;
  }
  
  .sessions-list::-webkit-scrollbar-thumb {
    background: #555;
    border-radius: 3px;
  }
  
  .session-item {
    padding: 12px;
    margin-bottom: 8px;
    background: linear-gradient(135deg, #363636, #313131);
    border-radius: 12px;
    cursor: pointer;
    border: 1px solid transparent;
    position: relative;
    transition: all 0.3s ease;
  }
  
  .session-item:hover {
    background: linear-gradient(135deg, #404040, #383838);
    transform: translateX(5px);
    box-shadow: 0 4px 15px rgba(0, 0, 0, 0.3);
    border-color: #4a90e2;
  }
  
  .session-item.active {
    background: linear-gradient(135deg, #4a90e2, #357abd);
    border-color: #4a90e2;
    box-shadow: 0 4px 20px rgba(74, 144, 226, 0.4);
  }
  
  .session-title {
    font-size: 14px;
    font-weight: 500;
    margin-bottom: 4px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  
  .session-meta {
    font-size: 12px;
    color: #aaa;
  }
  
  .delete-btn {
    position: absolute;
    top: 8px;
    right: 8px;
    background: linear-gradient(135deg, #ff4757, #ff3742);
    color: white;
    border: none;
    border-radius: 50%;
    width: 20px;
    height: 20px;
    font-size: 12px;
    cursor: pointer;
    opacity: 0;
    transition: all 0.2s ease;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  
  .session-item:hover .delete-btn {
    opacity: 1;
  }
  
  .delete-btn:hover {
    transform: scale(1.1);
    box-shadow: 0 2px 8px rgba(255, 71, 87, 0.4);
  }
  
  .main-content {
    flex: 1;
    display: flex;
    flex-direction: column;
    background: #1a1a1a;
    color: white;
  }
  
  .chat-header {
    padding: 25px;
    border-bottom: 1px solid #444;
    background: linear-gradient(135deg, #1f1f1f, #242424);
    box-shadow: 0 2px 10px rgba(0, 0, 0, 0.3);
    display: flex;
    flex-direction: column;
    align-items: flex-start;
  }
  
  .chat-header h2 {
    color: #4a90e2;
    margin-bottom: 5px;
  }
  
  .chat-header p {
    color: #aaa;
    font-size: 14px;
  }
  
  .chat-messages {
    flex: 1;
    overflow-y: auto;
    padding: 20px;
    display: flex;
    flex-direction: column;
    gap: 16px;
  }
  
  .chat-messages::-webkit-scrollbar {
    width: 6px;
  }
  
  .chat-messages::-webkit-scrollbar-track {
    background: #333;
  }
  
  .chat-messages::-webkit-scrollbar-thumb {
    background: #555;
    border-radius: 3px;
  }
  
  .message {
    max-width: 70%;
    padding: 12px 16px;
    border-radius: 18px;
    font-size: 14px;
    line-height: 1.4;
    animation: fadeInUp 0.3s ease-out;
  }
  
  @keyframes fadeInUp {
    from {
      opacity: 0;
      transform: translateY(20px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }
  
  .message.user {
    align-self: flex-end;
    background: linear-gradient(135deg, #4a90e2, #357abd);
    color: white;
    box-shadow: 0 4px 15px rgba(74, 144, 226, 0.3);
  }
  
  .message.assistant {
    align-self: flex-start;
    background: #333;
    color: #f0f0f0;
    border: 1px solid #555;
    box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2);
  }
  
  .voice-controls {
    padding: 30px;
    border-top: 1px solid #444;
    background: #2a2a2a;
    display: flex;
    justify-content: center;
    align-items: center;
    gap: 30px;
  }
  
  .mic-button {
    width: 70px;
    height: 70px;
    border-radius: 50%;
    border: none;
    display: flex;
    justify-content: center;
    align-items: center;
    cursor: pointer;
    transition: all 0.3s ease;
    position: relative;
    box-shadow: 0 8px 25px rgba(0, 0, 0, 0.3);
    font-size: 28px;
  }
  
  .mic-button.recording {
    background: linear-gradient(135deg, #ff4757, #ff3742);
    color: white;
    animation: pulse 1.5s ease-in-out infinite;
    box-shadow: 0 8px 30px rgba(255, 71, 87, 0.4);
  }
  
  .mic-button.idle {
    background: linear-gradient(135deg, #4a90e2, #357abd);
    color: white;
    box-shadow: 0 8px 30px rgba(74, 144, 226, 0.4);
  }
  
  .mic-button.waiting {
    background: linear-gradient(135deg, #ffa500, #ff8c00);
    color: white;
    box-shadow: 0 8px 30px rgba(255, 165, 0, 0.4);
  }
  
  .mic-button:disabled {
    background: #555;
    cursor: not-allowed;
    box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2);
  }
  
  .mic-button:not(:disabled):hover {
    transform: translateY(-3px);
    box-shadow: 0 12px 35px rgba(74, 144, 226, 0.5);
  }
  
  .mic-button:not(:disabled):active {
    transform: translateY(-1px);
  }
  
  /* 마이크 아이콘 스타일 */
  .mic-icon {
    font-size: 24px;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  
  .status-text {
    font-size: 16px;
    color: #4a90e2;
    font-weight: 500;
  }
  
  .empty-state {
    flex: 1;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    color: #aaa;
    text-align: center;
  }
  
  .empty-state h3 {
    margin-bottom: 15px;
    font-size: 24px;
    color: #4a90e2;
  }
  
  .empty-state p {
    font-size: 16px;
    line-height: 1.5;
  }
  
  /* 웨이브 효과를 위한 추가 스타일 */
  .wave-container {
    position: relative;
    display: flex;
    justify-content: center;
    align-items: center;
  }
  
  .wave-ring {
    position: absolute;
    border-radius: 50%;
    transition: all 0.2s ease-out;
  }
  
  .wave-ring-1 {
    width: 120px;
    height: 120px;
    background: radial-gradient(circle, transparent 0%, rgba(74, 144, 226, 0.1) 40%, rgba(74, 144, 226, 0.05) 70%, transparent 100%);
  }
  
  .wave-ring-2 {
    width: 100px;
    height: 100px;
    background: radial-gradient(circle, transparent 0%, rgba(74, 144, 226, 0.2) 30%, rgba(74, 144, 226, 0.08) 70%, transparent 100%);
    animation-delay: 0.2s;
  }
  
  .wave-ring-3 {
    width: 80px;
    height: 80px;
    background: radial-gradient(circle, transparent 0%, rgba(74, 144, 226, 0.3) 20%, rgba(74, 144, 226, 0.15) 60%, transparent 100%);
    animation-delay: 0.4s;
  }
`;

// --- 스타일 동적 삽입 ---
// 서버 사이드 렌더링(SSR) 환경에서는 document가 없으므로, 브라우저 환경에서만 실행되도록 확인합니다.
if (typeof document !== 'undefined') {
  // 기존 스타일이 있다면 제거하여 중복 삽입을 방지합니다.
  const existingStyle = document.getElementById('voice-chat-styles');
  if (existingStyle) {
    existingStyle.remove();
  }
  
  const styleSheet = document.createElement("style");
  styleSheet.id = 'voice-chat-styles';
  styleSheet.innerText = styles;
  document.head.appendChild(styleSheet);
}

/**
 * 음성 채팅 애플리케이션의 메인 컴포넌트입니다.
 * UI, 상태 관리, API 연동, WebSocket 통신 등 모든 프론트엔드 로직을 포함합니다.
 */
function App() {
  // --- React 상태(State) 및 참조(Ref) 관리 ---

  // 세션 및 사용자 정보
  const [currentUserId, setCurrentUserId] = useState(null);       // 현재 사용자의 고유 ID
  const [currentSession, setCurrentSession] = useState(null);   // 현재 활성화된 대화 세션 정보
  const [sessions, setSessions] = useState([]);                 // 사용자의 모든 대화 세션 목록
  const [messages, setMessages] = useState([]);                 // 현재 세션의 메시지 목록

  // UI 및 통신 상태
  const [recording, setRecording] = useState(false);            // 음성 녹음 중인지 여부
  const [connectionStatus, setConnectionStatus] = useState("연결중..."); // WebSocket 연결 상태
  const [isWaitingForResponse, setIsWaitingForResponse] = useState(false); // AI 응답 대기 중인지 여부
  const [isPlayingTTS, setIsPlayingTTS] = useState(false);        // AI 음성(TTS) 재생 중인지 여부

  // DOM 요소나 재렌더링에 영향을 주지 않는 값들을 저장하기 위한 Ref
  const mediaRecorderRef = useRef(null); // MediaRecorder 인스턴스 저장
  const audioChunksRef = useRef([]);     // 녹음된 오디오 데이터(chunk) 조각들 저장
  const ws = useRef(null);               // WebSocket 인스턴스 저장

  /**
   * (API 호출) 현재 사용자의 모든 세션 목록을 서버로부터 불러옵니다.
   */
  const loadSessions = useCallback(async () => {
    if (!currentUserId) return;
    
    try {
      const protocol = window.location.protocol;
      const baseUrl = `${protocol}//localhost:8000`; // 백엔드 주소
      const response = await fetch(`${baseUrl}/api/sessions/${currentUserId}`);
      const data = await response.json();
      setSessions(data.sessions || []);
    } catch (error) {
      console.error("세션 목록 로드에 실패했습니다:", error);
    }
  }, [currentUserId]);

  /**
   * 컴포넌트가 처음 마운트될 때 실행됩니다.
   * - localStorage에서 사용자 ID를 가져오거나, 없으면 새로 생성하여 저장합니다.
   * - 이를 통해 브라우저별로 고유한 사용자를 유지합니다.
   */
  useEffect(() => {
    let userId = localStorage.getItem('voice_chat_user_id');
    if (!userId) {
      userId = `user_${Date.now()}_${Math.random().toString(36).substr(2, 6)}`;
      localStorage.setItem('voice_chat_user_id', userId);
    }
    setCurrentUserId(userId);
    console.log(`👤 사용자 ID가 초기화되었습니다: ${userId}`);
  }, []);

  /**
   * 사용자 ID(currentUserId)가 설정되면 `loadSessions`를 호출하여
   * 해당 사용자의 세션 목록을 불러옵니다.
   */
  useEffect(() => {
    if (currentUserId) {
      loadSessions();
    }
  }, [currentUserId, loadSessions]);

  /**
   * (API 호출) '새 대화' 버튼 클릭 시, 서버에 새로운 세션 생성을 요청합니다.
   * 성공 시, 새 세션으로 UI 상태를 업데이트하고 WebSocket 연결을 시작합니다.
   */
  const startNewChat = async () => {
    if (!currentUserId) return;
    
    try {
      const protocol = window.location.protocol;
      const baseUrl = `${protocol}//localhost:8000`;
      const response = await fetch(`${baseUrl}/api/sessions/new`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: currentUserId })
      });
      const data = await response.json();
      
      await loadSessions(); // 세션 목록 다시 로드
      
      const newSession = {
        session_id: data.session_id,
        user_id: data.user_id,
        title: "새로운 대화",
        total_messages: 0
      };
      
      setCurrentSession(newSession); // 현재 세션을 새 것으로 교체
      setMessages([]);               // 메시지 목록 초기화
      
      connectWebSocket(data.user_id, data.session_id); // 새 세션으로 WebSocket 연결
      
    } catch (error) {
      console.error("새 대화 시작에 실패했습니다:", error);
    }
  };

  /**
   * (API 호출) 특정 세션의 모든 메시지 기록을 서버에서 불러옵니다.
   */
  const loadSessionMessages = async (sessionId) => {
    try {
      const protocol = window.location.protocol;
      const baseUrl = `${protocol}//localhost:8000`;
      const response = await fetch(`${baseUrl}/api/sessions/${sessionId}/messages`);
      const data = await response.json();
      setMessages(data.messages || []);
    } catch (error) {
      console.error("메시지 로드에 실패했습니다:", error);
    }
  };

  /**
   * 사용자가 사이드바에서 특정 세션을 클릭했을 때 호출됩니다.
   * - UI 상태를 해당 세션 정보로 업데이트합니다.
   * - 해당 세션의 메시지를 불러옵니다.
   * - WebSocket 연결을 새로운 세션 ID로 다시 설정합니다.
   */
  const selectSession = (session) => {
    setCurrentSession(session);
    loadSessionMessages(session.session_id);
    
    if (ws.current) {
      ws.current.close();
    }
    connectWebSocket(session.user_id, session.session_id);
  };

  /**
   * (API 호출) 특정 세션을 삭제합니다.
   */
  const deleteSession = async (sessionId, event) => {
    event.stopPropagation(); // 이벤트 버블링 방지
    
    if (!window.confirm("이 대화를 정말 삭제하시겠습니까?")) return;
    
    try {
      const protocol = window.location.protocol;
      const baseUrl = `${protocol}//localhost:8000`;
      await fetch(`${baseUrl}/api/sessions/${sessionId}`, { method: 'DELETE' });
      
      await loadSessions(); // 세션 목록 새로고침
      
      if (currentSession?.session_id === sessionId) {
        setCurrentSession(null);
        setMessages([]);
      }
    } catch (error) {
      console.error("세션 삭제에 실패했습니다:", error);
    }
  };

  /**
   * 백엔드 서버와 WebSocket 연결을 설정하고 이벤트 핸들러를 등록합니다.
   */
  const connectWebSocket = useCallback((user_id, session_id) => {
    if (!user_id || !session_id) return;

    // 기존 연결이 있다면 종료
    if (ws.current) {
        ws.current.close();
    }
      
    try {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${protocol}//localhost:8000/ws?user_id=${user_id}&session_id=${session_id}`;
      
      console.log(`[WebSocket] 연결 시도: ${wsUrl}`);
      const socket = new WebSocket(wsUrl);
      ws.current = socket; // ref에 소켓 인스턴스 저장
      
      // 연결 성공 시
      socket.onopen = () => {
        console.log("[WebSocket] 연결이 성공적으로 수립되었습니다.");
        setConnectionStatus("연결됨");
      };

      // 에러 발생 시
      socket.onerror = (err) => {
        console.error("[WebSocket] 연결 오류 발생:", err);
        setConnectionStatus("연결 실패");
      };

      // 연결 종료 시
      socket.onclose = (evt) => {
        console.log(`[WebSocket] 연결이 종료되었습니다. 코드: ${evt.code}, 이유: ${evt.reason}`);
        setConnectionStatus("연결 끊어짐");
        setIsWaitingForResponse(false);
      };

      // 서버로부터 메시지 수신 시
      socket.onmessage = (e) => {
        try {
          const msg = JSON.parse(e.data);
          console.log("[WebSocket] 메시지 수신:", msg);

          // 서버로부터 받은 메시지 타입에 따라 분기 처리
          if (msg.type === "response") {
            // AI의 최종 응답 (텍스트 + 오디오)
            setIsWaitingForResponse(false);
            
            // 대화창에 사용자 입력과 AI 응답 메시지 추가
            setMessages(prev => [...prev, 
              { role: 'user', content: msg.user_input },
              { role: 'assistant', content: msg.text }
            ]);

            // Howler.js를 사용하여 수신된 TTS 오디오 재생
            setIsPlayingTTS(true);
            const sound = new Howl({
              src: [`data:audio/wav;base64,${msg.audio}`],
              format: ['wav'],
              autoplay: true,
              onend: () => setIsPlayingTTS(false),
              onloaderror: () => {
                  console.error("[Howl] TTS 오디오 재생에 실패했습니다.");
                  setIsPlayingTTS(false);
              }
            });
            sound.play();

          } else if (msg.type === "info" || msg.type === "error") {
            // 정보 또는 오류 메시지 수신 시 (e.g., 음성 인식 실패)
            alert(msg.message);
            setIsWaitingForResponse(false);
          }
        } catch (error) {
          console.error("[WebSocket] 메시지 처리 중 오류 발생:", error);
          setIsWaitingForResponse(false);
        }
      };
      
    } catch (error) {
      console.error("[WebSocket] 소켓 생성 중 오류 발생:", error);
      setConnectionStatus("연결 실패");
    }
  }, []);

  /**
   * 마이크 버튼을 눌렀을 때 음성 녹음을 시작하고,
   * 녹음이 중지되면 오디오 데이터를 WebSocket을 통해 서버로 전송합니다.
   */
  const startRecord = async () => {
    // 녹음 시작 전 조건 확인
    if (!ws.current || ws.current.readyState !== WebSocket.OPEN) {
      alert("서버와 연결되지 않았습니다. 새 대화를 시작해주세요.");
      return;
    }
    if (isPlayingTTS || isWaitingForResponse || recording) return;

    try {
      // 마이크 권한 요청 및 미디어 스트림 가져오기
      const stream = await navigator.mediaDevices.getUserMedia({ 
        audio: { // 오디오 처리 옵션
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        } 
      });

      // MediaRecorder 설정
      const mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
      mediaRecorderRef.current = mediaRecorder;
      audioChunksRef.current = []; // 이전 녹음 데이터 초기화

      // 녹음 데이터가 들어올 때마다 chunks 배열에 추가
      mediaRecorder.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      // 녹음이 중지되었을 때 실행될 로직
      mediaRecorder.onstop = () => {
        setRecording(false);
        const audioBlob = new Blob(audioChunksRef.current, { type: "audio/webm" });
        
        // Blob 데이터를 Base64로 인코딩하여 서버에 전송
        const reader = new FileReader();
        reader.onloadend = () => {
          const base64data = reader.result.split(',')[1];
          
          if (ws.current && ws.current.readyState === WebSocket.OPEN) {
            ws.current.send(JSON.stringify({ 
              type: "audio", 
              data: base64data,
            }));
            setIsWaitingForResponse(true); // AI 응답 대기 상태로 전환
          }
        };
        reader.readAsDataURL(audioBlob);
        
        // 사용이 끝난 미디어 스트림 트랙 정리
        stream.getTracks().forEach(track => track.stop());
      };

      mediaRecorder.start();
      setRecording(true);
      
      // 3초 후 자동으로 녹음 중지 (사용자가 별도로 중지하지 않을 경우)
      setTimeout(() => {
        if (mediaRecorderRef.current && mediaRecorderRef.current.state === "recording") {
          mediaRecorderRef.current.stop();
        }
      }, 9000);

    } catch (err) {
      console.error("[녹음] 마이크 권한 획득 또는 녹음 시작에 실패했습니다:", err);
      alert("마이크 권한을 허용해주세요. 이 기능은 HTTPS 환경에서만 동작할 수 있습니다.");
    }
  };

  /**
   * 컴포넌트가 언마운트될 때 WebSocket 연결을 정리합니다.
   */
  useEffect(() => {
    return () => {
      if (ws.current) {
        ws.current.close();
      }
    };
  }, []);

  // --- 동적 UI 렌더링을 위한 헬퍼 함수들 ---

  /** 현재 상태에 따라 마이크 버튼의 CSS 클래스를 반환합니다. */
  const getMicButtonClass = () => {
    if (recording) return "mic-button recording";         // 녹음 중
    if (isWaitingForResponse || isPlayingTTS) return "mic-button waiting"; // 대기 또는 재생 중
    return "mic-button idle";                            // 유휴 상태
  };

  /** 현재 상태에 맞는 안내 텍스트를 반환합니다. */
  const getStatusText = () => {
    if (recording) return "듣고 있는 중...";
    if (isWaitingForResponse) return "AI가 생각하고 있어요...";
    if (isPlayingTTS) return "AI가 답변하고 있어요...";
    if (!currentSession) return "새 대화를 시작하거나 기존 대화를 선택해주세요.";
    return "마이크 버튼을 눌러 대화를 시작하세요.";
  };

  /** 현재 상태에 맞는 상태 텍스트의 색상을 반환합니다. */
  const getStatusColor = () => {
    if (recording) return "#ff4757"; // 빨간색
    if (isWaitingForResponse || isPlayingTTS) return "#ffa500"; // 주황색
    return "#4a90e2"; // 파란색
  };

  /** 녹음 중일 때 마이크 버튼 주위에 퍼지는 웨이브 애니메이션을 렌더링합니다. */
  const renderMicButtonWithWaves = () => {
    const isDisabled = !ws.current || ws.current.readyState !== WebSocket.OPEN || isPlayingTTS || isWaitingForResponse;

    const button = (
        <button
          className={getMicButtonClass()}
          onClick={startRecord}
          disabled={isDisabled}
        >
          <div className="mic-icon">🎤</div>
        </button>
    );

    if (recording) {
        return (
          <div className="wave-container">
            <div className="wave-ring wave-ring-1 pulse-animation"></div>
            <div className="wave-ring wave-ring-2 pulse-animation"></div>
            <div className="wave-ring wave-ring-3 pulse-animation"></div>
            {button}
          </div>
        );
    }
    return button;
  };

  // --- 최종 JSX 렌더링 ---
  return (
    <div className="chat-container">
      {/* 왼쪽 사이드바: 새 대화 버튼 및 세션 목록 */}
      <div className="sidebar">
        <div className="sidebar-header">
          <button className="new-chat-btn" onClick={startNewChat} disabled={!currentUserId || isWaitingForResponse || isPlayingTTS}>
            + 새 대화 시작하기
          </button>
        </div>
        
        <div className="sessions-list">
          {sessions.length === 0 ? (
            <div style={{ padding: '20px', textAlign: 'center', color: '#aaa' }}>
              진행중인 대화가 없습니다.
            </div>
          ) : (
            sessions.map((session) => (
              <div
                key={session.session_id}
                className={`session-item ${currentSession?.session_id === session.session_id ? 'active' : ''}`}
                onClick={() => selectSession(session)}
              >
                <div className="session-title">{session.title || `대화 #${session.session_id.slice(-4)}`}</div>
                <div className="session-meta">
                  {new Date(session.created_at).toLocaleDateString()}
                </div>
                <button 
                  className="delete-btn"
                  onClick={(e) => deleteSession(session.session_id, e)}
                  title="대화 삭제"
                >
                  ×
                </button>
              </div>
            ))
          )}
        </div>
      </div>

      {/* 오른쪽 메인 콘텐츠: 채팅창 및 음성 컨트롤 */}
      <div className="main-content">
        <div className="chat-header">
          <h2>{currentSession?.title || "AI 음성 비서"}</h2>
          <p>
            <span style={{ color: connectionStatus === "연결됨" ? "#4CAF50" : "#ff4757", fontWeight: 'bold' }}>
              ● {connectionStatus}
            </span>
            {currentUserId && ` | 사용자: ${currentUserId.substring(0, 15)}...`}
          </p>
        </div>

        {/* 현재 선택된 세션이 없을 때 보여주는 초기 화면 */}
        {!currentSession ? (
          <div className="empty-state">
            <h3>🎙️ AI 음성 채팅</h3>
            <p>좌측 상단의 '새 대화 시작하기' 버튼을 눌러 AI와 대화를 시작하세요.<br/>
            기존 대화 목록에서 대화를 이어갈 수도 있습니다.</p>
          </div>
        ) : (
          <>
            {/* 메시지 표시 영역 */}
            <div className="chat-messages">
              {messages.length === 0 ? (
                <div className="empty-state">
                  <h3>🚀 대화를 시작하세요</h3>
                  <p>아래의 마이크 버튼을 누르고 말씀하시면<br/>AI가 듣고 답변해 드립니다.</p>
                </div>
              ) : (
                messages.map((message, index) => (
                  <div
                    key={index}
                    className={`message ${message.role}`} // user 또는 assistant 클래스 부여
                  >
                    {message.content}
                  </div>
                ))
              )}
            </div>

            {/* 하단 음성 컨트롤 영역 */}
            <div className="voice-controls">
              {renderMicButtonWithWaves()}
              <div className="status-text" style={{ color: getStatusColor() }}>
                {getStatusText()}
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export default App;