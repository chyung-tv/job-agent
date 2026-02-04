import { createRouteHandler } from "uploadthing/next";

import { ourFileRouter } from "./core";

/**
 * UploadThing API route handler.
 * 
 * Handles GET and POST requests to /api/uploadthing
 * for file upload operations.
 */
export const { GET, POST } = createRouteHandler({
  router: ourFileRouter,
});
