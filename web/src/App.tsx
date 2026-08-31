import { Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { Compare } from "./routes/Compare";
import { Eval } from "./routes/Eval";
import { Explore } from "./routes/Explore";
import { Home } from "./routes/Home";
import { NotFound } from "./routes/NotFound";
import { Sandbox } from "./routes/Sandbox";
import { Tutorial } from "./routes/Tutorial";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Home />} />
        <Route path="explore" element={<Explore />} />
        <Route path="compare" element={<Compare />} />
        <Route path="tutorial/:arch" element={<Tutorial />} />
        <Route path="sandbox" element={<Sandbox />} />
        <Route path="eval" element={<Eval />} />
        <Route path="404" element={<NotFound />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
