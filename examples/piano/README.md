# Orchestra Piano

A one-octave web piano built end to end by the Orchestra orchestrator
([run record](../../docs/demo/piano/README.md)). No dependencies.

```bash
cd examples/piano
python -m http.server 8000   # then open http://localhost:8000
node --test "*.test.mjs"     # 7 tests, Node.js 18+
```

Click or tap a key, use `A W S E D F T G Y H U J K`, or press **Play Ode to Joy**.
`?pressed=E4,G4` lights keys without sound.
