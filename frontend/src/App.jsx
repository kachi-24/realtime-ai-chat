import * as Sentry from "@sentry/react";
import { useCallback, useEffect, useRef, useState } from "react";
import "./App.css";
import { useSpeechRecognition } from "./useSpeechRecognition";

import {
  WS_URL,
  apiFetch,
  clearAccessToken,
  getAccessToken,
  login as loginApi,
  logout as logoutApi,
  refreshSession,
  register as registerApi,
} from "./api";

import VerifyEmail from "./VerifyEmail";


function captureAppError(error, context = {}) {
  Sentry.withScope((scope) => {
    scope.setTag("component", "App");

    Object.entries(context).forEach(([key, value]) => {
      scope.setExtra(key, value);
    });

    Sentry.captureException(
      error instanceof Error
        ? error
        : new Error(String(error))
    );
  });
}


function App() {

  // --------------------------------
  // Authentication
  // --------------------------------

  const [token, setToken] = useState(
    getAccessToken()
  );

  const [user, setUser] = useState(null);

  const [authInitializing, setAuthInitializing] =
    useState(true);

  const [showVerification, setShowVerification] =
    useState(
      window.location.pathname ===
      "/verify-email"
    );

  const [authMode, setAuthMode] = useState("login");

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const [authError, setAuthError] = useState("");
  const [authLoading, setAuthLoading] = useState(false);


  // --------------------------------
  // Chat
  // --------------------------------

  const [messages, setMessages] = useState([]);

  const [message, setMessage] = useState("");

  const [conversationId, setConversationId] = useState(null);

  const [isGenerating, setIsGenerating] = useState(false);

  const [socketConnected, setSocketConnected] = useState(false);

  const socketRef = useRef(null);


  // --------------------------------
  // Conversations
  // --------------------------------

  const [conversations, setConversations] = useState([]);


  // --------------------------------
  // Documents
  // --------------------------------

  const [selectedFile, setSelectedFile] = useState(null);

  const [uploading, setUploading] = useState(false);

  const [documents, setDocuments] = useState([]);

  const [uploadMessage, setUploadMessage] = useState("");



  // ==========================================
  // Restore session on load
  // ==========================================
  //
  // The access token lives only in memory (api.js), so
  // on every page load we need to ask the backend for a
  // fresh one using the HttpOnly refresh cookie, rather
  // than reading a token out of localStorage.
  // ==========================================

  useEffect(() => {

    async function restoreSession() {
      try {
        const session =
          await refreshSession();

        if (session?.access_token) {
          setToken(
            session.access_token
          );

          const response =
            await apiFetch(
              "/auth/me",
              {},
              false
            );

          if (response.ok) {
            setUser(
              await response.json()
            );
          }
        }
      } catch (error) {
        console.error(
          "Session restore failed:",
          error
        );

        captureAppError(error, {
          area: "session_restore",
        });

        clearAccessToken();
        setToken(null);
      } finally {
        setAuthInitializing(false);
      }
    }

    if (!showVerification) {
      restoreSession();
    } else {
      setAuthInitializing(false);
    }

  }, [showVerification]);



  // ==========================================
  // Authentication
  // ==========================================

  const handleAuth = async (event) => {

    event.preventDefault();

    setAuthError("");

    if (
      !email.trim() ||
      !password.trim()
    ) {
      setAuthError(
        "Email and password are required."
      );
      return;
    }

    setAuthLoading(true);

    try {

      if (authMode === "register") {

        const response =
          await registerApi(
            email.trim(),
            password
          );

        const data =
          await response.json();

        if (!response.ok) {
          throw new Error(
            data.detail ||
            "Registration failed"
          );
        }

        setEmail("");
        setPassword("");
        setAuthMode("login");

        setAuthError(
          "Account created. Check your email and verify your account before logging in."
        );

        return;
      }

      const data =
        await loginApi(
          email.trim(),
          password
        );

      if (!data?.access_token) {
        throw new Error(
          data?.detail ||
          "Login failed"
        );
      }

      setToken(
        data.access_token
      );

      const response =
        await apiFetch(
          "/auth/me",
          {},
          false
        );

      if (response.ok) {
        setUser(
          await response.json()
        );
      }

      setEmail("");
      setPassword("");

    } catch (error) {

      captureAppError(error, {
        area: "authentication",
        auth_mode: authMode,
      });

      setAuthError(
        error.message ||
        "Authentication failed"
      );

    } finally {

      setAuthLoading(false);

    }
  };



  // ==========================================
  // Logout
  // ==========================================

  const logout = async () => {

    if (socketRef.current) {
      socketRef.current.close();
      socketRef.current = null;
    }

    try {
      await logoutApi();
    } catch (error) {
      console.error(
        "Logout failed:",
        error
      );

      captureAppError(error, {
        area: "logout",
      });
    }

    clearAccessToken();

    setToken(null);
    setUser(null);
    setMessages([]);
    setConversationId(null);
    setConversations([]);
    setDocuments([]);
    setSocketConnected(false);

  };



  // ==========================================
  // Load documents + conversations on login
  // ==========================================
  //
  // Documents and conversations live in the database,
  // not in component state — every time the page loads
  // (fresh login, or a restored session), we need to
  // fetch them again instead of assuming they're still
  // sitting in memory.
  //
  // ==========================================

  useEffect(() => {

    if (!token) {
      return;
    }


    const loadDocuments = async () => {

      try {

        const response = await apiFetch(
          "/documents"
        );

        if (!response.ok) {
          return;
        }

        const data = await response.json();

        setDocuments(data);

      } catch (error) {

        console.error(
          "Failed to load documents:",
          error
        );

        captureAppError(error, {
          area: "load_documents",
        });

      }

    };


    const loadConversations = async () => {

      try {

        const response = await apiFetch(
          "/conversations"
        );

        if (!response.ok) {
          return;
        }

        const data = await response.json();

        setConversations(data);

      } catch (error) {

        console.error(
          "Failed to load conversations:",
          error
        );

        captureAppError(error, {
          area: "load_conversations",
        });

      }

    };


    loadDocuments();

    loadConversations();

  }, [token]);



  // ==========================================
  // Open a past conversation
  // ==========================================

  const openConversation = async (id) => {

    if (isGenerating) {
      return;
    }

    try {

      const response = await apiFetch(
        `/conversations/${id}/messages`
      );

      if (!response.ok) {
        throw new Error(
          "Could not load that conversation."
        );
      }

      const data = await response.json();

      setConversationId(id);

      setMessages(
        data.map((message) => ({
          role: message.role,
          content: message.content,
          sources: [],
        }))
      );

    } catch (error) {

      console.error(
        "Failed to open conversation:",
        error
      );

      captureAppError(error, {
        area: "open_conversation",
        conversation_id: id,
      });

    }

  };



  // ==========================================
  // WebSocket
  // ==========================================

  useEffect(() => {

    if (!token) {
      return;
    }


    const socketUrl =
      `${WS_URL}/ws/chat?token=${encodeURIComponent(token)}`;


    const socket = new WebSocket(
      socketUrl
    );


    socketRef.current = socket;


    socket.onopen = () => {

      console.log(
        "WebSocket connected"
      );

      setSocketConnected(true);

    };


    socket.onmessage = (event) => {

      try {

        const data = JSON.parse(
          event.data
        );


        // ------------------------------
        // Conversation
        // ------------------------------

        if (
          data.type === "conversation"
        ) {

          setConversationId(
            (previousId) => {

              // If this conversation ID is new
              // (a brand new conversation was
              // just created), refresh the
              // sidebar list so it appears
              // without needing a page reload.
              if (
                previousId !==
                data.conversation_id
              ) {

                apiFetch("/conversations")
                  .then((response) =>
                    response.ok
                      ? response.json()
                      : null
                  )
                  .then((refreshed) => {
                    if (refreshed) {
                      setConversations(
                        refreshed
                      );
                    }
                  })
                  .catch((error) => {
                    console.error(
                      "Failed to refresh conversations:",
                      error
                    );

                    captureAppError(error, {
                      area: "refresh_conversations",
                    });
                  });

              }

              return data.conversation_id;

            }
          );

        }


        // ------------------------------
        // Sources
        // ------------------------------

        else if (
          data.type === "sources"
        ) {

          setMessages(
            previous => {

              const updated = [
                ...previous,
              ];

              const lastIndex =
                updated.length - 1;


              if (
                lastIndex >= 0 &&
                updated[lastIndex].role === "assistant"
              ) {

                updated[lastIndex] = {
                  ...updated[lastIndex],
                  sources: data.sources || [],
                };

              }

              return updated;

            }
          );

        }


        // ------------------------------
        // AI chunk
        // ------------------------------

        else if (
          data.type === "chunk"
        ) {

          setMessages(
            previous => {

              const updated = [
                ...previous,
              ];

              const lastIndex =
                updated.length - 1;


              if (
                lastIndex >= 0 &&
                updated[lastIndex].role === "assistant"
              ) {

                updated[lastIndex] = {
                  ...updated[lastIndex],

                  content:
                    updated[lastIndex].content +
                    data.content,

                };

              }

              return updated;

            }
          );

        }


        // ------------------------------
        // Done
        // ------------------------------

        else if (
          data.type === "done"
        ) {

          setIsGenerating(false);

        }


        // ------------------------------
        // Error
        // ------------------------------

        else if (
          data.type === "error"
        ) {

          console.error(
            data.message
          );


          setMessages(
            previous => {

              const updated = [
                ...previous,
              ];

              const lastIndex =
                updated.length - 1;


              if (
                lastIndex >= 0 &&
                updated[lastIndex].role === "assistant"
              ) {

                updated[lastIndex] = {
                  ...updated[lastIndex],

                  content:
                    `Error: ${data.message}`,

                };

              }

              return updated;

            }
          );


          setIsGenerating(false);

        }

      } catch (error) {

        console.error(
          "WebSocket message error:",
          error
        );

        captureAppError(error, {
          area: "websocket_message",
          conversation_id: conversationId,
        });

      }

    };


    socket.onerror = (error) => {

      console.error(
        "WebSocket error:",
        error
      );

      captureAppError(
        new Error("WebSocket connection error"),
        {
          area: "websocket_connection",
          conversation_id: conversationId,
          ready_state: socket.readyState,
        }
      );

      setSocketConnected(false);

    };


    socket.onclose = (event) => {

      console.log(
        "WebSocket disconnected",
        event.code,
        event.reason
      );

      if (event.code !== 1000 && event.code !== 1001) {
        captureAppError(
          new Error(
            `WebSocket closed unexpectedly (code ${event.code})`
          ),
          {
            area: "websocket_close",
            close_code: event.code,
            close_reason: event.reason || "",
            conversation_id: conversationId,
          }
        );
      }

      setSocketConnected(false);

    };


    return () => {

      socket.close();

    };

  }, [token]);



  // ==========================================
  // Send Message
  // ==========================================

  const sendMessage = (overrideText) => {

    const trimmedMessage =
      (overrideText ?? message).trim();


    if (!trimmedMessage) {
      return;
    }


    if (!socketRef.current) {

      alert(
        "WebSocket is not connected."
      );

      return;

    }


    if (
      socketRef.current.readyState !==
      WebSocket.OPEN
    ) {

      alert(
        "WebSocket is not connected."
      );

      return;

    }


    if (isGenerating) {
      return;
    }


    // ------------------------------
    // Add user message
    // ------------------------------

    setMessages(
      previous => [
        ...previous,

        {
          role: "user",
          content: trimmedMessage,
        },

        {
          role: "assistant",
          content: "",
          sources: [],
        },

      ]
    );


    // ------------------------------
    // Send to backend
    // ------------------------------

    socketRef.current.send(
      JSON.stringify({
        conversation_id:
          conversationId,

        message:
          trimmedMessage,
      })
    );


    setMessage("");

    setIsGenerating(true);

  };



  // ==========================================
  // Speech Recognition
  // ==========================================
  //
  // - While the user is talking, the live/interim
  //   transcript fills the message textarea so they
  //   can see what's being picked up.
  // - Once the hook detects ~2 seconds of silence, it
  //   reports a final transcript, which we auto-send
  //   as a message — no need to click Send.
  //
  // sendMessageRef always points at the latest
  // sendMessage (which closes over current state like
  // conversationId/isGenerating). Without this ref, the
  // memoized handleSpeechFinal below would auto-send
  // using a stale, outdated sendMessage.
  // ==========================================

  const sendMessageRef = useRef(() => {});

  useEffect(() => {
    sendMessageRef.current = sendMessage;
  });

  const handleSpeechTranscript = useCallback(
    (transcript) => {
      setMessage(transcript);
    },
    []
  );

  const handleSpeechFinal = useCallback(
    (finalTranscript) => {
      sendMessageRef.current(finalTranscript);
    },
    []
  );

  const {
    isListening,
    isSupported: speechSupported,
    error: speechError,
    startListening,
    stopListening,
  } = useSpeechRecognition({
    onTranscript: handleSpeechTranscript,
    onSilenceTimeout: handleSpeechFinal,
  });

  useEffect(() => {
    if (!speechError) {
      return;
    }

    captureAppError(
      new Error(speechError),
      {
        area: "speech_recognition",
      }
    );
  }, [speechError]);

  const toggleListening = () => {
    if (isListening) {
      stopListening();
    } else {
      setMessage("");
      startListening();
    }
  };



  // ==========================================
  // Enter key
  // ==========================================

  const handleKeyDown = (event) => {

    if (
      event.key === "Enter" &&
      !event.shiftKey
    ) {

      event.preventDefault();

      sendMessage();

    }

  };



  // ==========================================
  // New Conversation
  // ==========================================

  const newConversation = () => {

    setConversationId(null);

    setMessages([]);

  };



  // ==========================================
  // File Selection
  // ==========================================

  const handleFileChange = (event) => {

    const file =
      event.target.files?.[0];


    if (!file) {
      return;
    }


    const extension =
      file.name
        .split(".")
        .pop()
        ?.toLowerCase();


    if (
      extension !== "pdf" &&
      extension !== "txt"
    ) {

      setUploadMessage(
        "Only PDF and TXT files are supported."
      );

      setSelectedFile(null);

      return;

    }


    setSelectedFile(file);

    setUploadMessage("");

  };



  // ==========================================
  // Upload Document
  // ==========================================

  const uploadDocument = async () => {

    if (!selectedFile) {

      setUploadMessage(
        "Please select a PDF or TXT file."
      );

      return;

    }


    setUploading(true);

    setUploadMessage("");


    const formData =
      new FormData();


    formData.append(
      "file",
      selectedFile
    );


    try {

      const response =
        await apiFetch(
          "/documents/upload",
          {
            method: "POST",
            body: formData,
          }
        );


      const data =
        await response.json();


      if (!response.ok) {

        throw new Error(
          data.detail ||
          "Document upload failed"
        );

      }


      setUploadMessage(
        `Uploaded ${data.filename}. Processing document...`
      );


      setSelectedFile(null);


      const fileInput =
        document.getElementById(
          "document-file"
        );


      if (fileInput) {
        fileInput.value = "";
      }


      checkDocumentStatus(
        data.document_id
      );

    } catch (error) {

      captureAppError(error, {
        area: "document_upload",
        filename: selectedFile?.name || "unknown",
      });

      setUploadMessage(
        error.message ||
        "Document upload failed"
      );

    } finally {

      setUploading(false);

    }

  };



  // ==========================================
  // Check document processing
  // ==========================================

  const checkDocumentStatus = async (
    documentId
  ) => {

    try {

      const response =
        await apiFetch(
          `/documents/${documentId}`
        );


      const data =
        await response.json();


      if (!response.ok) {
        return;
      }


      setDocuments(
        previous => {

          const exists =
            previous.some(
              document =>
                document.document_id ===
                data.document_id
            );


          if (exists) {

            return previous.map(
              document =>
                document.document_id ===
                data.document_id
                  ? data
                  : document
            );

          }


          return [
            ...previous,
            data,
          ];

        }
      );


      if (
        data.status === "processing"
      ) {

        setTimeout(
          () => {
            checkDocumentStatus(
              documentId
            );
          },
          2000
        );

      }

      else if (
        data.status === "ready"
      ) {

        setUploadMessage(
          `${data.filename} is ready for RAG.`
        );

      }

      else if (
        data.status === "failed"
      ) {

        setUploadMessage(
          `Processing failed: ${
            data.error || "Unknown error"
          }`
        );

      }

    } catch (error) {

      console.error(
        "Document status error:",
        error
      );

      captureAppError(error, {
        area: "document_status",
        document_id: documentId,
      });

    }

  };



  // ==========================================
  // Render: Email Verification Page
  // ==========================================

  if (showVerification) {
    return (
      <VerifyEmail
        onLogin={() => {
          setShowVerification(false);
          setAuthMode("login");

          window.history.replaceState(
            {},
            "",
            "/"
          );
        }}
      />
    );
  }



  // ==========================================
  // Render: Restoring Session
  // ==========================================

  if (authInitializing) {
    return (
      <div className="auth-page">
        <div className="auth-card">
          <h1>
            Real-Time AI Chat
          </h1>

          <p className="auth-subtitle">
            Restoring your secure session...
          </p>
        </div>
      </div>
    );
  }



  // ==========================================
  // Render Authentication
  // ==========================================

  if (!token) {

    return (
      <div className="auth-page">

        <div className="auth-card">

          <h1>
            Real-Time AI Chat
          </h1>

          <p className="auth-subtitle">
            AI-powered RAG assistant
          </p>


          <div className="auth-tabs">

            <button
              className={
                authMode === "login"
                  ? "active"
                  : ""
              }

              onClick={() => {

                setAuthMode("login");

                setAuthError("");

              }}
            >
              Login
            </button>


            <button
              className={
                authMode === "register"
                  ? "active"
                  : ""
              }

              onClick={() => {

                setAuthMode("register");

                setAuthError("");

              }}
            >
              Register
            </button>

          </div>


          <form
            onSubmit={handleAuth}
          >

            <input
              type="email"
              placeholder="Email"
              value={email}
              onChange={(event) =>
                setEmail(
                  event.target.value
                )
              }
              required
            />


            <input
              type="password"
              placeholder="Password"
              value={password}
              onChange={(event) =>
                setPassword(
                  event.target.value
                )
              }
              required
            />


            {authError && (
              <div className="error">
                {authError}
              </div>
            )}


            <button
              className="primary-button"
              type="submit"
              disabled={authLoading}
            >

              {authLoading
                ? "Please wait..."
                : authMode === "login"
                  ? "Login"
                  : "Create Account"}

            </button>

          </form>

        </div>

      </div>
    );

  }



  // ==========================================
  // Main Application
  // ==========================================

  return (

    <div className="app">

      {/* ================================
          Header
      ================================= */}

      <header className="header">

        <div>

          <h1>
            Real-Time AI Chat
          </h1>

          <span className="user-email">
            {user?.email}
          </span>

        </div>


        <div className="header-actions">

          <span
            className={
              socketConnected
                ? "connection connected"
                : "connection disconnected"
            }
          >

            {socketConnected
              ? "● Connected"
              : "● Disconnected"}

          </span>


          <button
            onClick={logout}
            className="logout-button"
          >
            Logout
          </button>

        </div>

      </header>



      {/* ================================
          Main Layout
      ================================= */}

      <main className="main-layout">


        {/* =================================
            Sidebar
        ================================= */}

        <aside className="sidebar">

          <button
            className="new-chat-button"
            onClick={newConversation}
          >
            + New Conversation
          </button>


          {/* ===============================
              Conversations
          =============================== */}

          <section className="conversations-section">

            <h2>
              Conversations
            </h2>

            <div className="conversation-list">

              {conversations.length === 0 ? (

                <p className="empty">
                  No past conversations.
                </p>

              ) : (

                conversations.map(
                  (conversation) => (

                    <button
                      key={conversation.id}
                      className={
                        `conversation-item ${
                          conversation.id === conversationId
                            ? "active"
                            : ""
                        }`
                      }
                      onClick={() =>
                        openConversation(
                          conversation.id
                        )
                      }
                      disabled={isGenerating}
                    >

                      <strong>
                        {conversation.title}
                      </strong>

                      <span className="conversation-item-time">
                        {new Date(
                          conversation.updated_at
                        ).toLocaleString()}
                      </span>

                    </button>

                  )
                )

              )}

            </div>

          </section>


          {/* ===============================
              Documents
          =============================== */}

          <section className="documents-section">

            <h2>
              Documents
            </h2>


            <input
              id="document-file"
              type="file"
              accept=".pdf,.txt"
              onChange={
                handleFileChange
              }
            />


            {selectedFile && (

              <p className="selected-file">

                {selectedFile.name}

              </p>

            )}


            <button
              className="upload-button"
              onClick={uploadDocument}
              disabled={
                uploading ||
                !selectedFile
              }
            >

              {uploading
                ? "Uploading..."
                : "Upload Document"}

            </button>


            {uploadMessage && (

              <div className="upload-message">

                {uploadMessage}

              </div>

            )}


            <div className="document-list">

              {documents.length === 0 ? (

                <p className="empty">
                  No documents uploaded.
                </p>

              ) : (

                documents.map(
                  document => (

                    <div
                      key={
                        document.document_id
                      }
                      className="document-item"
                    >

                      <strong>
                        {document.filename}
                      </strong>

                      <span
                        className={
                          `status ${document.status}`
                        }
                      >
                        {document.status}
                      </span>

                    </div>

                  )
                )

              )}

            </div>

          </section>

        </aside>



        {/* =================================
            Chat
        ================================= */}

        <section className="chat-container">


          {/* Messages */}

          <div className="messages">

            {messages.length === 0 ? (

              <div className="welcome">

                <h2>
                  Welcome 👋
                </h2>

                <p>
                  Upload a document and ask
                  questions about it.
                </p>

                <p>
                  You can also ask general
                  questions using the local AI.
                </p>

              </div>

            ) : (

              messages.map(
                (msg, index) => (

                  <div
                    key={index}
                    className={
                      `message-row ${msg.role}`
                    }
                  >

                    <div
                      className={
                        `message-bubble ${msg.role}`
                      }
                    >

                      <div className="message-role">

                        {msg.role === "user"
                          ? "You"
                          : "AI"}

                      </div>


                      <div className="message-content">

                        {msg.content ||
                          (
                            msg.role ===
                              "assistant" &&
                            isGenerating
                          )
                          ? msg.content
                          : "Thinking..."}

                      </div>


                      {/* =====================
                          Sources
                      ===================== */}

                      {msg.role ===
                        "assistant" &&
                        msg.sources?.length > 0 && (

                        <div className="sources">

                          <h4>
                            Sources
                          </h4>


                          {msg.sources.map(
                            (source, sourceIndex) => (

                              <div
                                key={
                                  sourceIndex
                                }
                                className="source-item"
                              >

                                <div className="source-item-filename">
                                  📄{" "}
                                  {source.filename ||
                                    "Document"}
                                </div>

                                <div className="source-item-chunk">
                                  Chunk{" "}
                                  {source.chunk_index}
                                </div>

                              </div>

                            )
                          )}

                        </div>

                      )}

                    </div>

                  </div>

                )
              )

            )}

          </div>



          {/* ================================
              Message Input
          ================================= */}

          <div className="input-container">

            <textarea
              value={message}
              onChange={(event) =>
                setMessage(
                  event.target.value
                )
              }
              onKeyDown={handleKeyDown}
              placeholder={
                isListening
                  ? "Listening... speak now"
                  : socketConnected
                  ? "Ask something..."
                  : "Connecting to AI..."
              }
              disabled={
                !socketConnected ||
                isGenerating
              }
            />


            {speechSupported && (

              <button
                type="button"
                onClick={toggleListening}
                disabled={
                  !socketConnected ||
                  isGenerating
                }
                className={
                  `mic-button ${
                    isListening ? "listening" : ""
                  }`
                }
                title={
                  isListening
                    ? "Stop voice input"
                    : "Start voice input"
                }
              >
                {isListening ? "⏹️" : "🎤"}
              </button>

            )}


            <button
              onClick={() => sendMessage()}
              disabled={
                !socketConnected ||
                !message.trim() ||
                isGenerating
              }
              className="send-button"
            >

              {isGenerating
                ? "Generating..."
                : "Send"}

            </button>

          </div>

          {isListening && (
            <div className="speech-status">
              🎙️ Listening...
            </div>
          )}

          {speechError && (
            <div className="speech-error">
              {speechError}
            </div>
          )}

        </section>

      </main>

    </div>

  );

}


export default App;