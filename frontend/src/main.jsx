   import * as Sentry from "@sentry/react";
   import React from "react";
   import ReactDOM from "react-dom/client";
   import { GoogleOAuthProvider } from "@react-oauth/google";
   import App from "./App";
   import { AuthProvider } from "./AuthContext";

   Sentry.init({
     dsn: import.meta.env.VITE_SENTRY_DSN,

     environment:
       import.meta.env.VITE_ENVIRONMENT || "development",

     integrations: [
       Sentry.browserTracingIntegration(),
     ],

     tracesSampleRate: Number(
       import.meta.env.VITE_SENTRY_TRACES_SAMPLE_RATE || "0.1"
     ),

     sendDefaultPii: false,
   });

   const googleClientId = import.meta.env.VITE_GOOGLE_CLIENT_ID;

   const app = (
     <AuthProvider>
       <App />
     </AuthProvider>
   );

   ReactDOM.createRoot(
     document.getElementById("root")
   ).render(
     <React.StrictMode>
       {googleClientId ? (
         <GoogleOAuthProvider clientId={googleClientId}>
           {app}
         </GoogleOAuthProvider>
       ) : (
         app
       )}
     </React.StrictMode>
   );