import ReactMarkdown from "react-markdown";

export function ChatMarkdown({ content }: { content: string }) {
  return (
    <ReactMarkdown
      components={{
        a: ({ children, ...props }) => (
          <a {...props} target="_blank" rel="noreferrer">
            {children}
          </a>
        ),
      }}
    >
      {content}
    </ReactMarkdown>
  );
}
