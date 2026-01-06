import { useState, useEffect, type RefObject } from 'react'

interface ScrollToTopButtonProps {
  scrollRef: RefObject<HTMLDivElement | null>
  threshold?: number // pixels from top before button appears
}

export function ScrollToTopButton({ scrollRef, threshold = 300 }: ScrollToTopButtonProps) {
  const [isVisible, setIsVisible] = useState(false)

  useEffect(() => {
    const scrollElement = scrollRef.current
    if (!scrollElement) return

    const handleScroll = () => {
      setIsVisible(scrollElement.scrollTop > threshold)
    }

    scrollElement.addEventListener('scroll', handleScroll, { passive: true })
    // Check initial state
    handleScroll()

    return () => scrollElement.removeEventListener('scroll', handleScroll)
  }, [scrollRef, threshold])

  const scrollToTop = () => {
    scrollRef.current?.scrollTo({
      top: 0,
      behavior: 'smooth',
    })
  }

  if (!isVisible) return null

  return (
    <button
      onClick={scrollToTop}
      className="fixed bottom-6 right-6 p-3 rounded-full bg-accent-primary text-white shadow-lg hover:bg-accent-primary/90 transition-all duration-200 z-50"
      aria-label="Scroll to top"
      title="Scroll to top"
    >
      <ChevronUpIcon />
    </button>
  )
}

function ChevronUpIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <polyline points="18 15 12 9 6 15" />
    </svg>
  )
}
