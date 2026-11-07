import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import type { Ad } from '../api/types'

/** Рекламный баннер. Стоит в потоке страницы под контентом — очередь не перекрывает. */
export function AdBanner() {
  const { data } = useQuery({
    queryKey: ['ad'],
    queryFn: () => api<Ad | null>('/ads/active'),
    staleTime: 5 * 60_000,
    retry: false,
  })
  if (!data) return null
  return (
    <aside className="ad" aria-label="Реклама">
      <a href={data.link} target="_blank" rel="noopener noreferrer sponsored">
        <img src={data.image_url} alt="Реклама" loading="lazy" />
      </a>
      <span className="ad-label">реклама</span>
    </aside>
  )
}
