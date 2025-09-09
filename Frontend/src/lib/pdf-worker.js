import { pdfjs } from 'react-pdf'

// This points to the correct path in node_modules
pdfjs.GlobalWorkerOptions.workerSrc = `https://unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;
