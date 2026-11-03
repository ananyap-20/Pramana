import assert from 'node:assert/strict'
import { test } from 'node:test'
import { readFile } from 'node:fs/promises'
import { createRequire } from 'node:module'
import { pathToFileURL } from 'node:url'
import vm from 'node:vm'
import { transformWithOxc } from 'vite'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'

const require = createRequire(import.meta.url)
const source = await readFile(new URL('../src/components/WelcomeTransition.tsx', import.meta.url), 'utf8')
let compiled = (await transformWithOxc(source, 'WelcomeTransition.tsx', { jsx: { runtime: 'automatic' } })).code
for (const name of ['react/jsx-runtime', 'react']) compiled = compiled.replaceAll(`from "${name}"`, `from ${JSON.stringify(pathToFileURL(require.resolve(name)).href)}`)
// Effects do not run in the server renderer; no API request should be needed to show the welcome.
compiled = compiled.replace(/import \{ getReadiness \} from ['"]\.\.\/api\/client['"];?/, 'const getReadiness = () => { throw new Error("Unexpected render-time API call") }')
const { WelcomeTransition } = await import('data:text/javascript;base64,' + Buffer.from(compiled).toString('base64'))

test('initial welcome renders the existing proportional mark, product name and accessible status', () => {
  const html = renderToStaticMarkup(createElement(WelcomeTransition, null, createElement('p', null, 'Main studio')))
  assert.match(html, /alt="Pramana P brand mark"/)
  assert.match(html, /src="\/favicon.svg"/)
  assert.match(html, /width="96" height="96"/)
  assert.match(html, />Pramana</)
  assert.match(html, /Welcome to your desk/)
  assert.match(html, /role="status"/)
  assert.doesNotMatch(html, /Main studio|Sign in|password|account/i)
})

test('module-load failure and timeout expose retry and never modify the mounted studio', async () => {
  const html = await readFile(new URL('../index.html', import.meta.url), 'utf8')
  const script = html.match(/<script>([\s\S]*?)<\/script>/)[1]
  const status = { textContent: '', setAttribute(name, value) { this[name] = value } }
  const retry = { hidden: true }
  let mounted = false
  let onError, timeout
  class HTMLScriptElement {}
  vm.runInNewContext(script, {
    HTMLScriptElement,
    document: { getElementById: (id) => mounted ? null : id === 'boot-status' ? status : retry },
    window: { addEventListener: (_, handler) => { onError = handler }, setTimeout: (handler) => { timeout = handler } },
  })
  onError({ target: new HTMLScriptElement() })
  assert.equal(retry.hidden, false)
  assert.equal(status.role, 'alert')
  assert.match(status.textContent, /could not load/)
  mounted = true
  assert.doesNotThrow(() => timeout())
})
