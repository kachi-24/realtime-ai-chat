import * as Sentry from "@sentry/react";
import { useEffect, useRef, useState } from "react";

// How long to wait after the user goes quiet before
// treating their speech as finished.
const SILENCE_TIMEOUT_MS = 2000;

export function useSpeechRecognition({
  language = "en-US",
  onTranscript,
  onSilenceTimeout,
}) {
  const recognitionRef = useRef(null);
  const silenceTimerRef = useRef(null);
  const latestTranscriptRef = useRef("");

  const [isListening, setIsListening] = useState(false);
  const [isSupported, setIsSupported] = useState(true);
  const [error, setError] = useState(null);

  const clearSilenceTimer = () => {
    if (silenceTimerRef.current) {
      clearTimeout(silenceTimerRef.current);
      silenceTimerRef.current = null;
    }
  };

  useEffect(() => {
    const SpeechRecognition =
      window.SpeechRecognition ||
      window.webkitSpeechRecognition;

    // Speech recognition isn't available in every browser.
    // This is expected behavior, so don't report it as
    // an application exception.
    if (!SpeechRecognition) {
      setIsSupported(false);
      return;
    }

    const recognition = new SpeechRecognition();

    recognition.lang = language;
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.maxAlternatives = 1;

    recognition.onstart = () => {
      setIsListening(true);
      setError(null);
      latestTranscriptRef.current = "";

      Sentry.addBreadcrumb({
        category: "speech",
        message: "Speech recognition started",
        level: "info",
        data: {
          language,
        },
      });
    };

    recognition.onresult = (event) => {
      let transcript = "";

      for (
        let i = event.resultIndex;
        i < event.results.length;
        i++
      ) {
        transcript +=
          event.results[i][0].transcript;
      }

      latestTranscriptRef.current = transcript;

      onTranscript(transcript);

      // Every time new speech comes in, restart
      // the silence timer.
      clearSilenceTimer();

      silenceTimerRef.current = setTimeout(() => {
        if (recognitionRef.current) {
          recognitionRef.current.stop();
        }
      }, SILENCE_TIMEOUT_MS);
    };

    recognition.onerror = (event) => {
      console.error(
        "Speech recognition error:",
        event.error
      );

      // Browser speech-recognition errors are often
      // expected user/browser conditions.
      if (event.error === "not-allowed") {
        setError(
          "Microphone permission was denied."
        );
      } else if (event.error === "no-speech") {
        setError(
          "No speech was detected."
        );
      } else {
        setError(
          `Speech recognition error: ${event.error}`
        );
      }

      // Capture unexpected speech-recognition errors.
      if (
        event.error !== "not-allowed" &&
        event.error !== "no-speech"
      ) {
        Sentry.captureMessage(
          `Speech recognition error: ${event.error}`,
          "warning"
        );
      }

      setIsListening(false);
      clearSilenceTimer();
    };

    recognition.onend = () => {
      setIsListening(false);
      clearSilenceTimer();

      const finalTranscript =
        latestTranscriptRef.current.trim();

      if (
        finalTranscript &&
        onSilenceTimeout
      ) {
        onSilenceTimeout(
          finalTranscript
        );
      }

      latestTranscriptRef.current = "";

      Sentry.addBreadcrumb({
        category: "speech",
        message: "Speech recognition ended",
        level: "info",
      });
    };

    recognitionRef.current =
      recognition;

    return () => {
      clearSilenceTimer();

      try {
        recognition.abort();
      } catch (error) {
        Sentry.captureException(error, {
          tags: {
            operation:
              "speech_recognition_cleanup",
          },
        });
      }

      recognitionRef.current = null;
    };
  }, [
    language,
    onTranscript,
    onSilenceTimeout,
  ]);

  const startListening = () => {
    if (
      !recognitionRef.current ||
      isListening
    ) {
      return;
    }

    setError(null);

    try {
      recognitionRef.current.start();
    } catch (error) {
      console.error(
        "Could not start speech recognition:",
        error
      );

      Sentry.captureException(
        error,
        {
          tags: {
            operation:
              "speech_recognition_start",
          },

          extra: {
            language,
          },
        }
      );

      setError(
        "Could not start speech recognition."
      );
    }
  };

  const stopListening = () => {
    if (!recognitionRef.current) {
      return;
    }

    try {
      recognitionRef.current.stop();
    } catch (error) {
      console.error(
        "Could not stop speech recognition:",
        error
      );

      Sentry.captureException(
        error,
        {
          tags: {
            operation:
              "speech_recognition_stop",
          },
        }
      );
    }
  };

  return {
    isListening,
    isSupported,
    error,
    startListening,
    stopListening,
  };
}