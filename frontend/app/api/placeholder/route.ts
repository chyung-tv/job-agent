import { NextResponse } from "next/server";

/**
 * Placeholder API endpoint for onboarding submission.
 * 
 * This is a temporary endpoint that logs the payload and returns a success response.
 * It will be replaced with the actual workflow API endpoint in the future.
 */
export async function POST(request: Request) {
  try {
    const payload = await request.json();

    // Log the payload to console
    console.log("Onboarding submission payload:", JSON.stringify(payload, null, 2));

    // Return success response
    return NextResponse.json(
      {
        success: true,
        message: "Onboarding data received successfully",
        data: payload,
      },
      { status: 200 }
    );
  } catch (error) {
    console.error("Error processing placeholder request:", error);
    return NextResponse.json(
      {
        success: false,
        message: "Failed to process request",
        error: error instanceof Error ? error.message : "Unknown error",
      },
      { status: 500 }
    );
  }
}
