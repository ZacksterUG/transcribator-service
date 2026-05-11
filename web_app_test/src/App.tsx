import { Route, Routes } from "react-router-dom";
import { Header } from "./pages/Header";
import { HomePage } from "./pages/HomePage";
import { AsyncPage } from "./pages/AsyncPage";
import { AsyncResultPage } from "./pages/AsyncResultPage";
import { SyncPage } from "./pages/SyncPage";
import { ForbiddenPage } from "./pages/ForbiddenPage";
import { ProtectedRoute } from "./components/ProtectedRoute";

function NotFound() {
  return <div>Страница не найдена</div>;
}

function App() {
  return (
    <>
      <Header />
      <Routes>
        <Route path="/" element={<HomePage />} />
        
        <Route
          path="/async"
          element={
            <ProtectedRoute requiredRoles={["transcriber_web_test_app_user"]}>
              <AsyncPage />
            </ProtectedRoute>
          }
        />
        
        <Route
          path="/async/result/:jobId"
          element={
            <ProtectedRoute requiredRoles={["transcriber_web_test_app_user"]}>
              <AsyncResultPage />
            </ProtectedRoute>
          }
        />
        
        <Route
          path="/sync"
          element={
            <ProtectedRoute requiredRoles={["transcriber_web_test_app_user"]}>
              <SyncPage />
            </ProtectedRoute>
          }
        />
        
        <Route path="/forbidden" element={<ForbiddenPage />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </>
  );
}

export default App;