// Optional developer check: node tools/verify_core.mjs
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import {fileURLToPath} from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const read = filename => fs.readFileSync(path.join(root, filename), 'utf8');
const context = {fixture: JSON.parse(read('examples/core_fixture.json'))};
vm.createContext(context);
vm.runInContext(read('attention_lab/static/core.js'), context);
vm.runInContext(read('tests/verify_core.js'), context);
new vm.Script(read('attention_lab/static/app.js'));
console.log(JSON.stringify(context.coreTestReport, null, 2));
