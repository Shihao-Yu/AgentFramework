/// <reference types="vite/client" />

declare module '*.css?inline' {
  const content: string
  export default content
}

declare module '@xyflow/react/dist/style.css?inline' {
  const content: string
  export default content
}
