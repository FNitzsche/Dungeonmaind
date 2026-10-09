import { expect, test } from '@playwright/test'

test.use({ headless: true })

test('renders the sample network and switches to session responses without leaking sample data', async ({
  page,
}) => {
  await page.addInitScript(() => {
    sessionStorage.setItem(
      'player',
      JSON.stringify({ id: 'map-test-player', name: 'Map tester', role: 'member' }),
    )
    localStorage.setItem('backendUrl', 'http://map-backend.test')
  })
  await page.route('http://map-backend.test/players/map-test-player/exists', (route) =>
    route.fulfill({ json: { exists: true } }),
  )
  const requests: { method: string; body: string | null }[] = []
  await page.route(/^http:\/\/map-backend\.test\/map(?:\/generate)?$/, (route) => {
    requests.push({ method: route.request().method(), body: route.request().postData() })
    return route.fulfill({ json: { nodes: [], edges: [], source_segment_count: 0 } })
  })
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))

  await page.goto('/map?demo=sample')
  await expect(
    page.getByText('Sample demo — invented data, not extracted session results.'),
  ).toBeVisible()
  await expect(page.locator('.graph-canvas canvas').first()).toBeVisible()
  await expect(page.getByRole('alert')).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Generate Map' })).toBeDisabled()
  expect(requests).toEqual([])

  await page.getByRole('button', { name: 'Willowbrook — 3 mentions' }).click()
  const details = page.getByRole('region', { name: 'Selection details' })
  await expect(details).toContainText('00:00:10')
  await page.getByRole('button', { name: 'Silverwood Forest → north of → Willowbrook' }).click()
  await expect(details).toContainText('Sample: Silverwood Forest lies north of Willowbrook.')
  await expect(details).toContainText('00:00:30')
  await page.getByRole('button', { name: 'Clear selection' }).click()
  await expect(details).toContainText('Select a location')
  await page.getByRole('button', { name: 'Fit to View' }).click()
  await page.screenshot({ path: test.info().outputPath('map-desktop.png'), fullPage: true })

  await page.setViewportSize({ width: 390, height: 844 })
  await expect(page.locator('.graph-canvas')).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  )
  await page.screenshot({ path: test.info().outputPath('map-mobile.png'), fullPage: true })

  await page.getByRole('button', { name: 'Use session data' }).click()
  await expect(page.getByText('No geographic map yet')).toBeVisible()
  await expect(page.getByText('Willowbrook', { exact: true })).toHaveCount(0)
  expect(requests).toEqual([{ method: 'GET', body: null }])
  await page.getByRole('button', { name: 'Generate Map' }).click()
  await expect(page.getByRole('button', { name: 'Generate Map' })).toBeEnabled()
  expect(requests).toEqual([
    { method: 'GET', body: null },
    { method: 'POST', body: null },
  ])
  await page.getByRole('button', { name: 'Show sample demo' }).click()
  await expect(page.locator('.graph-canvas canvas').first()).toBeVisible()
  await expect(details).toContainText('Select a location')
  expect(requests).toHaveLength(2)
  expect(errors).toEqual([])
})
