import { Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { Compare } from "./routes/Compare";
import { Eval } from "./routes/Eval";
import { Explore } from "./routes/Explore";
import { Home } from "./routes/Home";
import { NotFound } from "./routes/NotFound";
import { Sandbox } from "./routes/Sandbox";
import { Tutorial } from "./routes/Tutorial";

// GitHub Pages is a static file host with no server-side routing -- a
// direct load or refresh of e.g. /glassbox/tutorial/graph requests that
// exact path, finds no file there, and serves GitHub's own generic 404
// page before this router ever runs. web/package.json's `build` script
// copies dist/index.html to dist/404.html to work around this (GitHub
// Pages' documented SPA-fallback trick): GitHub serves that file for any
// unmatched path, which loads this same app, and *then* this router
// resolves the real path client-side -- to a real route, or to the `*`
// route below for a genuinely bad path.
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
