import { Routes, Route } from "react-router-dom";
import { SessionProvider } from "./context/SessionContext.tsx";
import ChatPage from "./pages/ChatPage.tsx";
import EvaluatePage from "./pages/EvaluatePage.tsx";

export default function App() {
  return (
    <Routes>
      <Route
        path="/"
        element={
          <SessionProvider>
            <ChatPage />
          </SessionProvider>
        }
      />
      <Route path="/evaluate" element={<EvaluatePage />} />
    </Routes>
  );
}
