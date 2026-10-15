import * as Sentry from "@sentry/react";
import {
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";

import "./App.css";

import { useSpeechRecognition } from "./useSpeechRecognition";

import {
  WS_URL,
  apiFetch,
  clearAccessToken,
  getAccessToken,
  googleLogin,
  login as loginApi,
  logout as logoutApi,
  refreshSession,
  register as registerApi,
} from "./api";

import VerifyEmail from "./VerifyEmail";

import { GoogleLogin } from "@react-oauth/google";

import { uploadImage } from "./api/images";


function captureAppError(error, context = {}) {
  Sentry.withScope((scope) => {
    scope.setTag("component", "App");

    Object.entries(context).forEach(
      ([key, value]) => {
        scope.setExtra(key, value);
      }
    );

    Sentry.captureException(
      error instanceof Error
        ? error
        : new Error(String(error))
    );
  });
}


function App() {

  // ==========================================
  // Authentication
  // ==========================================

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

  const [authMode, setAuthMode] =
    useState("login");

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const [authError, setAuthError] =
    useState("");

  const [authLoading, setAuthLoading] =
    useState(false);


  // ==========================================
  // Chat
  // ==========================================

  const [messages, setMessages] =
    useState([]);

  const [message, setMessage] =
    useState("");

  const [conversationId, setConversationId] =
    useState(null);

  const [isGenerating, setIsGenerating] =
    useState(false);

  const [socketConnected, setSocketConnected] =
    useState(false);

  const socketRef = useRef(null);


  // ==========================================
  // Conversations
  // ==========================================

  const [conversations, setConversations] =
    useState([]);


  // ==========================================
  // Documents
  // ==========================================

  const [selectedFile, setSelectedFile] =
    useState(null);

  const [uploading, setUploading] =
    useState(false);

  const [documents, setDocuments] =
    useState([]);

  const [uploadMessage, setUploadMessage] =
    useState("");


  // ==========================================
  // Images
  // ==========================================

  const [selectedImage, setSelectedImage] =
    useState(null);

  const [imagePreview, setImagePreview] =
    useState(null);

  const [uploadingImage, setUploadingImage] =
    useState(false);

  const [imageError, setImageError] =
    useState("");

  const [webSearch, setWebSearch] =
    useState(false);

  const [modelChoice, setModelChoice] =
    useState("ollama");


  // ==========================================
  // Restore Session
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
  // Google Sign-In
  // ==========================================

  const handleGoogleSuccess = async (
    credentialResponse
  ) => {

    setAuthError("");

    setAuthLoading(true);

    try {

      const data =
        await googleLogin(
          credentialResponse.credential
        );

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

    } catch (error) {

      captureAppError(error, {
        area: "google_login",
      });

      setAuthError(
        error.message ||
        "Google sign-in failed"
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

    setSelectedImage(null);

    setImagePreview(null);

    setSocketConnected(false);

  };


  // ==========================================
  // Load Documents + Conversations
  // ==========================================

  useEffect(() => {

    if (!token) {
      return;
    }


    const loadDocuments = async () => {

      try {

        const response =
          await apiFetch(
            "/documents"
          );

        if (!response.ok) {
          return;
        }

        const data =
          await response.json();

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

        const response =
          await apiFetch(
            "/conversations"
          );

        if (!response.ok) {
          return;
        }

        const data =
          await response.json();

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
  // Open Conversation
  // ==========================================

  const openConversation = async (id) => {

    if (isGenerating) {
      return;
    }

    try {

      const response =
        await apiFetch(
          `/conversations/${id}/messages`
        );

      if (!response.ok) {

        throw new Error(
          "Could not load that conversation."
        );

      }

      const data =
        await response.json();

      setConversationId(id);

      setMessages(
        data.map((item) => ({
          role: item.role,
          content: item.content,
          sources: [],
          image: null,
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

    const socket =
      new WebSocket(socketUrl);

    socketRef.current = socket;


    socket.onopen = () => {

      console.log(
        "WebSocket connected"
      );

      setSocketConnected(true);

    };


    socket.onmessage = (event) => {

      try {

        const data =
          JSON.parse(event.data);


        // ------------------------------
        // Conversation
        // ------------------------------

        if (
          data.type === "conversation"
        ) {

          setConversationId(
            (previousId) => {

              if (
                previousId !==
                data.conversation_id
              ) {

                apiFetch(
                  "/conversations"
                )
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

                    captureAppError(
                      error,
                      {
                        area:
                          "refresh_conversations",
                      }
                    );

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
            (previous) => {

              const updated =
                [...previous];

              const lastIndex =
                updated.length - 1;

              if (
                lastIndex >= 0 &&
                updated[lastIndex].role ===
                  "assistant"
              ) {

                updated[lastIndex] = {
                  ...updated[lastIndex],
                  sources:
                    data.sources || [],
                };

              }

              return updated;

            }
          );

        }


        // ------------------------------
        // AI Chunk
        // ------------------------------

        else if (
          data.type === "chunk"
        ) {

          setMessages(
            (previous) => {

              const updated =
                [...previous];

              const lastIndex =
                updated.length - 1;

              if (
                lastIndex >= 0 &&
                updated[lastIndex].role ===
                  "assistant"
              ) {

                updated[lastIndex] = {
                  ...updated[lastIndex],

                  content:
                    updated[lastIndex]
                      .content +
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


        else if (
          data.type === "reset"
        ) {

          setMessages(
            (previous) => {

              const updated =
                [...previous];

              const lastIndex =
                updated.length - 1;

              if (
                lastIndex >= 0 &&
                updated[lastIndex].role ===
                  "assistant"
              ) {

                updated[lastIndex] = {
                  ...updated[lastIndex],
                  content: "",
                };

              }

              return updated;

            }
          );

        }


        else if (
          data.type === "web_sources"
        ) {

          setMessages(
            (previous) => {

              const updated =
                [...previous];

              const lastIndex =
                updated.length - 1;

              if (
                lastIndex >= 0 &&
                updated[lastIndex].role ===
                  "assistant"
              ) {

                updated[lastIndex] = {
                  ...updated[lastIndex],
                  webSources:
                    data.sources || [],
                };

              }

              return updated;

            }
          );

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
            (previous) => {

              const updated =
                [...previous];

              const lastIndex =
                updated.length - 1;

              if (
                lastIndex >= 0 &&
                updated[lastIndex].role ===
                  "assistant"
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
          conversation_id:
            conversationId,
        });

      }

    };


    socket.onerror = () => {

      console.error(
        "WebSocket error"
      );

      captureAppError(
        new Error(
          "WebSocket connection error"
        ),
        {
          area:
            "websocket_connection",
          conversation_id:
            conversationId,
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

      if (
        event.code !== 1000 &&
        event.code !== 1001
      ) {

        captureAppError(
          new Error(
            `WebSocket closed unexpectedly (code ${event.code})`
          ),
          {
            area:
              "websocket_close",
            close_code:
              event.code,
            close_reason:
              event.reason || "",
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
  // Image Selection
  // ==========================================

  const handleImageChange = (event) => {

    const file =
      event.target.files?.[0];

    if (!file) {
      return;
    }

    setImageError("");


    const allowedTypes = [
      "image/jpeg",
      "image/png",
      "image/webp",
    ];

    const maxSize =
      10 * 1024 * 1024;


    if (!allowedTypes.includes(file.type)) {

      setImageError(
        "Only JPG, PNG, and WebP images are allowed."
      );

      event.target.value = "";

      return;
    }


    if (file.size > maxSize) {

      setImageError(
        "Image must be smaller than 10 MB."
      );

      event.target.value = "";

      return;
    }


    if (imagePreview) {

      URL.revokeObjectURL(
        imagePreview
      );

    }


    const preview =
      URL.createObjectURL(file);

    setSelectedImage(file);

    setImagePreview(preview);

  };


  const removeSelectedImage = () => {

    if (imagePreview) {

      URL.revokeObjectURL(
        imagePreview
      );

    }

    setSelectedImage(null);
    setImagePreview(null);
    setImageError("");

    const input =
      document.getElementById(
        "image-file"
      );

    if (input) {
      input.value = "";
    }

  };


  useEffect(() => {

    return () => {

      if (imagePreview) {

        URL.revokeObjectURL(
          imagePreview
        );

      }

    };

  }, [imagePreview]);


  // ==========================================
  // Send Message
  // ==========================================

  const sendMessage = async (
    overrideText
  ) => {

    const trimmedMessage =
      (
        overrideText ??
        message
      ).trim();


    if (
      !trimmedMessage &&
      !selectedImage
    ) {

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


    const outgoingText =
      trimmedMessage || "Describe this image.";

    let uploadedImageId = null;

    // Created after a successful upload, from the file itself.
    // The picker's own preview URL is revoked when the selection
    // is cleared, which would break the image in the chat bubble.
    let localImagePreview = null;


    // ======================================
    // Upload Image First
    // ======================================

    if (selectedImage) {

      try {

        setUploadingImage(true);

        setImageError("");

        const data =
          await uploadImage(
            selectedImage,
            apiFetch
          );

        uploadedImageId =
          data.image_id;

        localImagePreview =
          URL.createObjectURL(selectedImage);

      } catch (error) {

        console.error(
          "Image upload failed:",
          error
        );

        captureAppError(
          error,
          {
            area:
              "image_upload",
          }
        );

        setImageError(
          error.message ||
          "Image upload failed."
        );

        setUploadingImage(false);

        return;

      } finally {

        setUploadingImage(false);

      }

    }


    // ======================================
    // Add User + Assistant Message
    // ======================================

    setMessages(
      (previous) => [

        ...previous,

        {
          role: "user",
          content:
            outgoingText,
          image:
            localImagePreview,
        },

        {
          role: "assistant",
          content: "",
          sources: [],
          image: null,
        },

      ]
    );


    // ======================================
    // Send WebSocket Payload
    // ======================================

    socketRef.current.send(
      JSON.stringify({
        conversation_id:
          conversationId,

        message:
          outgoingText,

        image_id:
          uploadedImageId,

        web_search:
          webSearch,

        model:
          modelChoice,
      })
    );


    setMessage("");

    removeSelectedImage();

    setIsGenerating(true);

  };


  // ==========================================
  // Speech Recognition
  // ==========================================

  const sendMessageRef =
    useRef(() => {});


  useEffect(() => {

    sendMessageRef.current =
      sendMessage;

  });


  const handleSpeechTranscript =
    useCallback(
      (transcript) => {

        setMessage(
          transcript
        );

      },
      []
    );


  const handleSpeechFinal =
    useCallback(
      (finalTranscript) => {

        sendMessageRef.current(
          finalTranscript
        );

      },
      []
    );


  const {
    isListening,
    isSupported:
      speechSupported,
    error:
      speechError,
    startListening,
    stopListening,
  } =
    useSpeechRecognition({
      onTranscript:
        handleSpeechTranscript,

      onSilenceTimeout:
        handleSpeechFinal,
    });


  useEffect(() => {

    if (!speechError) {
      return;
    }

    captureAppError(
      new Error(speechError),
      {
        area:
          "speech_recognition",
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
  // Enter Key
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

    if (isGenerating) {
      return;
    }

    setConversationId(null);

    setMessages([]);

    removeSelectedImage();

  };


  // ==========================================
  // Document Selection
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

      captureAppError(
        error,
        {
          area:
            "document_upload",

          filename:
            selectedFile?.name ||
            "unknown",
        }
      );


      setUploadMessage(
        error.message ||
        "Document upload failed"
      );


    } finally {

      setUploading(false);

    }

  };


  // ==========================================
  // Check Document Status
  // ==========================================

  const checkDocumentStatus =
    async (documentId) => {

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
          (previous) => {

            const exists =
              previous.some(
                (document) =>
                  document.document_id ===
                  data.document_id
              );


            if (exists) {

              return previous.map(
                (document) =>
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
          data.status ===
          "processing"
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
          data.status ===
          "ready"
        ) {

          setUploadMessage(
            `${data.filename} is ready for RAG.`
          );

        }

        else if (
          data.status ===
          "failed"
        ) {

          setUploadMessage(
            `Processing failed: ${
              data.error ||
              "Unknown error"
            }`
          );

        }

      } catch (error) {

        console.error(
          "Document status error:",
          error
        );

        captureAppError(
          error,
          {
            area:
              "document_status",

            document_id:
              documentId,
          }
        );

      }

    };


  // ==========================================
  // Email Verification
  // ==========================================

  if (showVerification) {

    return (
      <VerifyEmail
        onLogin={() => {

          setShowVerification(
            false
          );

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
  // Restoring Session
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
  // Authentication
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

                setAuthMode(
                  "register"
                );

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
              disabled={
                authLoading
              }
            >

              {authLoading
                ? "Please wait..."
                : authMode === "login"
                ? "Login"
                : "Create Account"}

            </button>

          </form>


          {import.meta.env.VITE_GOOGLE_CLIENT_ID && (

            <div
              style={{
                marginTop: "16px",
                display: "flex",
                justifyContent: "center",
              }}
            >

              <GoogleLogin
                onSuccess={
                  handleGoogleSuccess
                }

                onError={() =>
                  setAuthError(
                    "Google sign-in failed"
                  )
                }
              />

            </div>

          )}

        </div>

      </div>
    );

  }


  // ==========================================
  // Main Application
  // ==========================================

  return (

    <div className="app">


      {/* ==================================
          Header
      ================================== */}

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


      {/* ==================================
          Main Layout
      ================================== */}

      <main className="main-layout">


        {/* ==================================
            Sidebar
        ================================== */}

        <aside className="sidebar">

          <button
            className="new-chat-button"
            onClick={
              newConversation
            }
          >
            + New Conversation
          </button>


          {/* Conversations */}

          <section className="conversations-section">

            <h2>
              Conversations
            </h2>


            <div className="conversation-list">

              {conversations.length ===
              0 ? (

                <p className="empty">
                  No past conversations.
                </p>

              ) : (

                conversations.map(
                  (conversation) => (

                    <button
                      key={
                        conversation.id
                      }

                      className={
                        `conversation-item ${
                          conversation.id ===
                          conversationId
                            ? "active"
                            : ""
                        }`
                      }

                      onClick={() =>
                        openConversation(
                          conversation.id
                        )
                      }

                      disabled={
                        isGenerating
                      }
                    >

                      <strong>
                        {
                          conversation.title
                        }
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


          {/* Documents */}

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
              onClick={
                uploadDocument
              }

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

              {documents.length ===
              0 ? (

                <p className="empty">
                  No documents uploaded.
                </p>

              ) : (

                documents.map(
                  (document) => (

                    <div
                      key={
                        document.document_id
                      }

                      className="document-item"
                    >

                      <strong>
                        {
                          document.filename
                        }
                      </strong>

                      <span
                        className={
                          `status ${document.status}`
                        }
                      >
                        {
                          document.status
                        }
                      </span>

                    </div>

                  )
                )

              )}

            </div>

          </section>

        </aside>


        {/* ==================================
            Chat
        ================================== */}

        <section className="chat-container">


          {/* Messages */}

          <div className="messages">

            {messages.length ===
            0 ? (

              <div className="welcome">

                <h2>
                  Welcome 👋
                </h2>

                <p>
                  Upload a document and
                  ask questions about it.
                </p>

                <p>
                  You can also ask
                  general questions using
                  the local AI.
                </p>

                <p>
                  📷 You can now attach
                  images for AI analysis.
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

                        {msg.role ===
                        "user"
                          ? "You"
                          : "AI"}

                      </div>


                      {/* Image */}

                      {msg.image && (

                        <div className="message-image">

                          <img
                            src={
                              msg.image
                            }
                            alt="Attached"
                          />

                        </div>

                      )}


                      {/* Message */}

                      <div className="message-content">

                        {msg.content ? (
                          msg.content
                        ) : (
                          msg.role ===
                            "assistant" &&
                          isGenerating
                            ? "Thinking..."
                            : ""
                        )}

                      </div>


                      {/* Web sources */}

                      {msg.webSources?.length > 0 && (

                        <div className="sources">

                          <h4>
                            Web sources
                          </h4>

                          {msg.webSources.map(
                            (source, sourceIndex) => (

                              <div
                                key={sourceIndex}
                                className="source-item"
                              >

                                <a
                                  href={source.url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                >
                                  [W{sourceIndex + 1}]{" "}
                                  {source.title || source.url}
                                </a>

                              </div>

                            )
                          )}

                        </div>

                      )}


                      {/* Sources */}

                      {msg.role ===
                        "assistant" &&
                        msg.sources?.length >
                          0 && (

                        <div className="sources">

                          <h4>
                            Sources
                          </h4>


                          {msg.sources.map(
                            (
                              source,
                              sourceIndex
                            ) => (

                              <div
                                key={
                                  sourceIndex
                                }

                                className="source-item"
                              >

                                <div className="source-item-filename">
                                  📄{" "}
                                  {
                                    source.filename ||
                                    "Document"
                                  }
                                </div>

                                <div className="source-item-chunk">
                                  Chunk{" "}
                                  {
                                    source.chunk_index
                                  }
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


          {/* ==================================
              Image Preview
          ================================== */}

          {imagePreview && (

            <div className="selected-image-container">

              <div className="selected-image-preview">

                <img
                  src={imagePreview}
                  alt="Selected"
                />

                <button
                  type="button"
                  onClick={
                    removeSelectedImage
                  }

                  className="remove-image-button"
                >
                  ×
                </button>

              </div>

              <div className="selected-image-info">

                <strong>
                  {selectedImage?.name}
                </strong>

                <span>
                  {selectedImage
                    ? `${(
                        selectedImage.size /
                        1024 /
                        1024
                      ).toFixed(2)} MB`
                    : ""}
                </span>

              </div>

            </div>

          )}


          {imageError && (

            <div className="image-error">
              {imageError}
            </div>

          )}


          {/* ==================================
              Input
          ================================== */}

          <div className="input-container">


            {/* Model */}

            <select
              value={modelChoice}
              onChange={(event) =>
                setModelChoice(
                  event.target.value
                )
              }
              disabled={isGenerating}
              title="Choose the AI model"
              style={{
                padding: "8px",
                borderRadius: "8px",
              }}
            >
              <option value="ollama">
                Local (Ollama)
              </option>
              <option value="api">
                Cloud (API)
              </option>
            </select>


            {/* Web Search */}

            <label
              title="Search the web for current information"
              style={{
                display: "flex",
                alignItems: "center",
                gap: "4px",
                fontSize: "14px",
                whiteSpace: "nowrap",
              }}
            >
              <input
                type="checkbox"
                checked={webSearch}
                onChange={(event) =>
                  setWebSearch(
                    event.target.checked
                  )
                }
                disabled={isGenerating}
              />
              🌐 Web
            </label>


            {/* Image Button */}

            <label
              htmlFor="image-file"
              className={
                `image-button ${
                  uploadingImage
                    ? "disabled"
                    : ""
                }`
              }

              title="Attach image"
            >
              📷
            </label>

            <input
              id="image-file"
              type="file"
              accept="image/jpeg,image/png,image/webp"
              onChange={
                handleImageChange
              }
              hidden
              disabled={
                uploadingImage ||
                isGenerating
              }
            />


            {/* Text */}

            <textarea
              value={message}

              onChange={(event) =>
                setMessage(
                  event.target.value
                )
              }

              onKeyDown={
                handleKeyDown
              }

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


            {/* Microphone */}

            {speechSupported && (

              <button
                type="button"

                onClick={
                  toggleListening
                }

                disabled={
                  !socketConnected ||
                  isGenerating
                }

                className={
                  `mic-button ${
                    isListening
                      ? "listening"
                      : ""
                  }`
                }

                title={
                  isListening
                    ? "Stop voice input"
                    : "Start voice input"
                }
              >

                {isListening
                  ? "⏹️"
                  : "🎤"}

              </button>

            )}


            {/* Send */}

            <button
              onClick={() =>
                sendMessage()
              }

              disabled={
                !socketConnected ||
                (
                  !message.trim() &&
                  !selectedImage
                ) ||
                isGenerating ||
                uploadingImage
              }

              className="send-button"
            >

              {uploadingImage
                ? "Uploading..."
                : isGenerating
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
