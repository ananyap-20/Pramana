export type IconName = 'edit' | 'check' | 'file' | 'history' | 'shield' | 'image' | 'arrow' | 'help' | 'user' | 'upload' | 'search'

const paths: Record<IconName, string> = {
  edit: 'M12 20h9M16.5 3.5a2.1 2.1 0 0 1 3 3L8 18l-4 1 1-4Z',
  check: 'm5 12 4 4L19 6',
  file: 'M14 2H5v20h14V7Zm0 0v6h5M8 12h8M8 16h6',
  history: 'M3 11a9 9 0 1 1 2.6 7M3 4v7h7M12 7v5l3 2',
  shield: 'm12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6Zm-4 9 3 3 5-6',
  image: 'M3 3h18v18H3Zm0 14 6-6 5 5 3-3 4 4M15 7h.01',
  arrow: 'M4 12h16m-6-6 6 6-6 6',
  help: 'M9.1 9a3 3 0 1 1 5.8 1c-.9 1.2-2.9 1.2-2.9 3m0 4h.01M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0',
  user: 'M20 21v-2a7 7 0 0 0-14 0v2M17 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0',
  upload: 'M12 16V3m-5 5 5-5 5 5M3 15v6h18v-6',
  search: 'm21 21-6-6M17 10a7 7 0 1 1-14 0 7 7 0 0 1 14 0',
}

export function Icon({ name }: { name: IconName }) {
  return <svg className="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[name]} /></svg>
}
