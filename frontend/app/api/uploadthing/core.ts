
import { createUploadthing, type FileRouter } from "uploadthing/next";

const f = createUploadthing();

// FileRouter for your app, can contain multiple FileRoutes
export const ourFileRouter = {
  // Define as many FileRoutes as you like, each with a unique routeSlug
  pdfUploader: f({
    pdf: {
      maxFileSize: "64MB", // Default for PDF, explicitly set for clarity
      maxFileCount: 5 //(default, allows 1 file per upload)
      // contentDisposition: "inline" (default)
    },
  })
    .onUploadComplete(async ({ file }) => {
      // This code RUNS ON YOUR SERVER after upload.
      // Metadata registration may fail (e.g. network) but file is already in storage;
      // we always return file.url so the client gets the direct link.
      try {
        console.log("Upload complete for file:", file.name);
        console.log("File URL:", file.url);
      } catch (err) {
        // Log but don't fail - metadata registration errors are non-critical
        console.warn("onUploadComplete log error (non-fatal):", err);
      }
      // !!! Whatever is returned here is sent to the clientside `onClientUploadComplete` callback
      return { uploadedBy: "user" };
    }),
} satisfies FileRouter;

export type OurFileRouter = typeof ourFileRouter;
