# Third-Party Notices

JARVIS bundles and adapts code from the projects listed below. Each notice is
reproduced in full as required by the applicable licence.

---

## Ultron Orb UI

- Upstream: <https://github.com/SAGAR-TAMANG/ultron-by-sagar-builds.git>
- Upstream files: `lib/orbScene.ts`, `lib/handTracker.ts`, `components/JarvisOrb.tsx`, `app/globals.css`
- Used by: `frontend/js/ui/orb-scene.js`, `frontend/js/ui/hand-tracker.js`, `frontend/js/ui/orb.js`, `frontend/css/orb.css`
- Licence: MIT

```
MIT License

Copyright (c) 2026 Sagar Tamang

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

### Local modifications

The upstream orb is a React component inside a Next.js application. JARVIS has
no Node build step, so it was adapted to plain browser ES modules:

- TypeScript types and interfaces were removed.
- React hooks (`useState`, `useEffect`, `useCallback`, `useRef`) were replaced
  with the existing JARVIS store, event bus and DOM helpers.
- Rendering was changed from a full-page takeover to an optional centre view
  toggled from the existing HUD.
- Brand strings were changed to `J.A.R.V.I.S.`.
- Orb behaviour is now driven by JARVIS' existing core states
  (`idle`, `listening`, `processing`, `executing`, `speaking`, `error`,
  `offline`) instead of a standalone timer.
- WebGL initialisation failure is caught and reported instead of throwing.
- Hand tracking became optional: the camera is probed before use, MediaPipe is
  fetched lazily only on demand, and the absence of a camera is reported as a
  non-blocking status.

---

## Three.js

- Upstream: <https://github.com/mrdoob/three.js>
- Upstream version: r185 (`0.185.1`)
- Used by: `frontend/vendor/three/`
- Licence: MIT

The vendored files in `frontend/vendor/three/` are unmodified copies from the
`three` npm package and retain their original licence headers:

```
/**
 * @license
 * Copyright 2010-2026 Three.js Authors
 * SPDX-License-Identifier: MIT
 */
```

```
MIT License

Copyright (c) 2010-2026 three.js authors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

## MediaPipe Tasks Vision

- Upstream: <https://github.com/google-ai-edge/mediapipe>
- Used by: `frontend/js/ui/hand-tracker.js` (loaded lazily from a CDN at runtime)
- Licence: Apache-2.0

MediaPipe is **not** bundled with JARVIS. It is fetched from
`cdn.jsdelivr.net` only if an operator enables hand gestures and a camera is
present, so it has no effect on JARVIS startup, offline use or licence
obligations. The hand-landmark model is likewise loaded at runtime from
`storage.googleapis.com`.
