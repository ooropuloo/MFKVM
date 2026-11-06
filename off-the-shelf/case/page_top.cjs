// Renders v3.html's real meshes from above with the CDC port away from the viewer, for test_handedness.py.
// usage: node page_top.cjs <v3.html> <out dir> <playwright-core path>
const path = require('path');
const fs = require('fs');
const { chromium } = require(process.argv[4]);
(async () => {
  const out = process.argv[3];
  const b = await chromium.launch({ channel: 'chrome', headless: true, args: ['--use-angle=d3d11', '--ignore-gpu-blocklist', '--allow-file-access-from-files'] });
  const p = await b.newPage({ viewport: { width: 700, height: 900 } });
  const errs = [];
  p.on('pageerror', (e) => errs.push(e.message));
  await p.goto('file:///' + path.resolve(process.argv[2]).replace(/\\/g, '/'), { waitUntil: 'load', timeout: 60000 });
  await p.waitForFunction(() => window.__ready, { timeout: 40000 });
  const res = await p.evaluate(() => {
    // the page's own objects, not a copy of its logic
    setMode('closed', true);
    Object.keys(P).forEach((k) => { P[k].visible = k === 'core_board' || k === 'core_parts'; });
    const size = new THREE.Vector2();
    renderer.getSize(size);
    const toWorld = (x, y, z) => root.localToWorld(new THREE.Vector3(x, y, z));
    const c = toWorld(0, 30, 0);
    const up = toWorld(0, 60, 0).sub(toWorld(0, 0, 0)).normalize();   // from the antenna end to the CDC end
    const halfH = 36, halfW = halfH * size.x / size.y;
    const cam = new THREE.OrthographicCamera(-halfW, halfW, halfH, -halfH, 1, 500);
    cam.up.copy(up);
    cam.position.set(c.x, c.y + 200, c.z);   // above the top side
    cam.lookAt(c);
    cam.updateMatrixWorld();
    renderer.render(scene, cam);
    const url = renderer.domElement.toDataURL('image/png');
    const px = (x, y, z) => { const v = toWorld(x, y, z).project(cam); return [(v.x + 1) / 2, (1 - v.y) / 2]; };
    // where the page really puts the geometry: the mesh vertices themselves, in world space
    const a = P.core_parts.children[0].geometry.attributes.position;
    let right = 0, left = 0;
    const v = new THREE.Vector3();
    for (let i = 0; i < a.count; i++) {
      v.fromBufferAttribute(a, i);
      if (v.y > 41 && v.y < 50 && v.z > 2.5 && v.z < 3.3) {
        const s = px(v.x, v.y, v.z)[0];
        if (s > px(0, 30, 0)[0]) right++; else left++;
      }
    }
    return { url, otg_screen: px(12.7, 45.5, 1.1), cdc_screen: px(0, 61, 1.1), rst_screen: px(-12.7, 53.3, 1.4), boot_screen: px(12.7, 53.3, 1.4), centre: px(0, 30, 0), mm_per_view_h: 2 * halfH, verts_otg_band_right: right, verts_otg_band_left: left, det: root.matrixWorld.determinant(), usesKicad: /kicad/i.test(document.documentElement.innerHTML.slice(0, 20000)) };
  });
  fs.writeFileSync(out + '/page_top.png', Buffer.from(res.url.split(',')[1], 'base64'));
  delete res.url;
  res.errors = errs;
  fs.writeFileSync(out + '/page_top.json', JSON.stringify(res, null, 1));
  console.log(JSON.stringify(res));
  await b.close();
})().catch((e) => { console.error(e); process.exit(1); });
