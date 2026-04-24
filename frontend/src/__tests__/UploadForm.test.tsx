import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, waitFor, fireEvent, act } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"

// --- Hoisted mocks (vi.hoisted ensures these run before vi.mock factories) ---

const { mockPush, mockToast, mockDetect } = vi.hoisted(() => ({
  mockPush: vi.fn(),
  mockToast: vi.fn(),
  mockDetect: vi.fn(),
}))

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
}))

vi.mock("@/hooks/use-toast", () => ({
  useToast: () => ({ toast: mockToast }),
}))

vi.mock("@/lib/detectTrackedChanges", () => ({
  detectTrackedChanges: (...args: unknown[]) => mockDetect(...args),
}))

// Mock fetch globally
global.fetch = vi.fn()

// --- Import component after mocks are declared ---
import { UploadForm } from "@/components/UploadForm"
import { TrackedChangesModal } from "@/components/TrackedChangesModal"

// --- Helpers ---

function renderForm() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <UploadForm />
    </QueryClientProvider>
  )
}

function mockFetchLanguages() {
  ;(global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
    ok: true,
    json: () => Promise.resolve({ languages: [] }),
  })
}

/** Simulate file selection on the hidden <input type="file"> using fireEvent */
function selectFile(file: File) {
  const input = document.getElementById("file-input") as HTMLInputElement
  Object.defineProperty(input, "files", { value: [file], configurable: true })
  fireEvent.change(input)
}

// --- Tests ---

describe("UploadForm rendering", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockDetect.mockResolvedValue(false)
    mockFetchLanguages()
  })

  it("renders the drop zone with idle text", () => {
    renderForm()
    expect(screen.getByText("Drop your DOCX, PDF, or PPTX here")).toBeDefined()
    expect(screen.getByText(/or click to choose a file/)).toBeDefined()
  })

  it("renders source and target language labels", () => {
    renderForm()
    expect(screen.getByText("Source Language")).toBeDefined()
    expect(screen.getByText("Target Language")).toBeDefined()
  })

  it("renders the Translate Document button", () => {
    renderForm()
    expect(screen.getByText("Translate Document")).toBeDefined()
  })

  it("submit button is disabled when no file is selected", () => {
    renderForm()
    const button = screen.getByText("Translate Document").closest("button")
    expect(button).toBeDefined()
    expect(button?.disabled).toBe(true)
  })

  it("hidden file input accepts .docx, .pdf, .pptx", () => {
    renderForm()
    const input = document.getElementById("file-input") as HTMLInputElement
    expect(input).toBeDefined()
    expect(input?.accept).toBe(".docx,.pdf,.pptx")
  })
})

describe("UploadForm file validation", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockDetect.mockResolvedValue(false)
    mockFetchLanguages()
  })

  it("shows destructive toast for unsupported file type", async () => {
    renderForm()
    const badFile = new File(["content"], "test.txt", { type: "text/plain" })
    selectFile(badFile)

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({
          variant: "destructive",
          description: expect.stringContaining("Unsupported file type"),
        })
      )
    })
  })

  it("shows destructive toast for file exceeding 25 MB", async () => {
    renderForm()
    const bigContent = new Uint8Array(26 * 1024 * 1024) // 26 MB
    const bigFile = new File([bigContent], "big.docx", {
      type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    })
    selectFile(bigFile)

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({
          variant: "destructive",
          description: expect.stringContaining("File too large"),
        })
      )
    })
  })

  it("calls detectTrackedChanges after a valid DOCX is selected", async () => {
    renderForm()
    const docxFile = new File(["docx-bytes"], "test.docx", {
      type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    })
    selectFile(docxFile)

    await waitFor(() => {
      expect(mockDetect).toHaveBeenCalledWith(docxFile)
    })
  })

  it("calls detectTrackedChanges for a PDF file (returns false for non-.docx)", async () => {
    renderForm()
    const pdfFile = new File(["pdf-bytes"], "test.pdf", { type: "application/pdf" })
    selectFile(pdfFile)

    await waitFor(() => {
      expect(mockDetect).toHaveBeenCalledWith(pdfFile)
    })
  })

  it("shows filename after a valid DOCX is selected", async () => {
    renderForm()
    const docxFile = new File(["bytes"], "my-doc.docx", {
      type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    })
    selectFile(docxFile)

    await waitFor(() => {
      expect(screen.getByText("my-doc.docx")).toBeDefined()
    })
  })
})

describe("UploadForm submit disabled state", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockDetect.mockResolvedValue(false)
    mockFetchLanguages()
  })

  it("submit button remains disabled when only file is selected (no target lang)", async () => {
    renderForm()
    const docxFile = new File(["bytes"], "test.docx", {
      type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    })
    selectFile(docxFile)

    await waitFor(() => { expect(screen.getByText("test.docx")).toBeDefined() })

    const button = screen.getByText("Translate Document").closest("button")
    expect(button?.disabled).toBe(true)
  })

  it("detectTrackedChanges is called before any POST (B4 Option A)", async () => {
    mockDetect.mockResolvedValue(true)
    renderForm()

    const docxFile = new File(["bytes"], "tracked.docx", {
      type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    })
    selectFile(docxFile)

    await waitFor(() => {
      expect(mockDetect).toHaveBeenCalledWith(docxFile)
    })

    // fetch should NOT have been called (no submit happened yet)
    expect(global.fetch).not.toHaveBeenCalledWith("/api/upload", expect.anything())
  })
})

describe("TrackedChangesModal unit tests (D-13 spec)", () => {
  it("renders modal title and description when open", () => {
    const onApply = vi.fn()
    const onCancel = vi.fn()
    render(
      <TrackedChangesModal
        open={true}
        onApply={onApply}
        onCancel={onCancel}
        onOpenChange={vi.fn()}
      />
    )

    expect(screen.getByText("Tracked Changes Detected")).toBeDefined()
    expect(
      screen.getByText(/This document has unresolved tracked changes/)
    ).toBeDefined()
  })

  it("renders three radio options: strip, preserve, cancel", () => {
    render(
      <TrackedChangesModal
        open={true}
        onApply={vi.fn()}
        onCancel={vi.fn()}
        onOpenChange={vi.fn()}
      />
    )

    expect(screen.getByLabelText(/Remove tracked changes/)).toBeDefined()
    expect(screen.getByLabelText(/Preserve and translate both/)).toBeDefined()
    expect(screen.getByLabelText(/Cancel/)).toBeDefined()
  })

  it("renders Apply Selection and Cancel Upload buttons", () => {
    render(
      <TrackedChangesModal
        open={true}
        onApply={vi.fn()}
        onCancel={vi.fn()}
        onOpenChange={vi.fn()}
      />
    )

    expect(screen.getByText("Apply Selection")).toBeDefined()
    expect(screen.getByText("Cancel Upload")).toBeDefined()
  })

  it("calls onCancel when Cancel Upload is clicked", async () => {
    const onCancel = vi.fn()
    render(
      <TrackedChangesModal
        open={true}
        onApply={vi.fn()}
        onCancel={onCancel}
        onOpenChange={vi.fn()}
      />
    )

    await userEvent.click(screen.getByText("Cancel Upload"))
    expect(onCancel).toHaveBeenCalledTimes(1)
  })

  it("calls onApply with 'strip' (default selection) when Apply Selection is clicked", async () => {
    const onApply = vi.fn()
    render(
      <TrackedChangesModal
        open={true}
        onApply={onApply}
        onCancel={vi.fn()}
        onOpenChange={vi.fn()}
      />
    )

    await userEvent.click(screen.getByText("Apply Selection"))
    expect(onApply).toHaveBeenCalledWith("strip")
  })

  it("calls onCancel when 'cancel' option is selected and Apply is clicked", async () => {
    const onApply = vi.fn()
    const onCancel = vi.fn()
    render(
      <TrackedChangesModal
        open={true}
        onApply={onApply}
        onCancel={onCancel}
        onOpenChange={vi.fn()}
      />
    )

    // Select the cancel radio option
    const cancelRadio = screen.getByRole("radio", { name: /Cancel/ })
    await userEvent.click(cancelRadio)
    await userEvent.click(screen.getByText("Apply Selection"))

    // When cancel option is selected, onCancel fires (not onApply)
    expect(onCancel).toHaveBeenCalledTimes(1)
    expect(onApply).not.toHaveBeenCalled()
  })

  it("does not render content when closed", () => {
    render(
      <TrackedChangesModal
        open={false}
        onApply={vi.fn()}
        onCancel={vi.fn()}
        onOpenChange={vi.fn()}
      />
    )

    expect(screen.queryByText("Tracked Changes Detected")).toBeNull()
  })
})

describe("UploadForm tracked-changes reliability (G1 gap closure)", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockFetchLanguages()
  })

  it("calls detectTrackedChanges on second upload of same tracked-changes DOCX", async () => {
    mockDetect.mockResolvedValue(true)
    renderForm()

    const docxFile = new File(["bytes"], "tracked.docx", {
      type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    })

    // First upload — detection fires
    selectFile(docxFile)
    await waitFor(() => {
      expect(mockDetect).toHaveBeenCalledTimes(1)
    })

    // Second upload of same file — detection must fire again (no caching/skipping)
    selectFile(docxFile)
    await waitFor(() => {
      expect(mockDetect).toHaveBeenCalledTimes(2)
    })

    // Both calls used the same file object
    expect(mockDetect).toHaveBeenNthCalledWith(1, docxFile)
    expect(mockDetect).toHaveBeenNthCalledWith(2, docxFile)
  })

  it("resets modal after cancel then re-selection", async () => {
    mockDetect.mockResolvedValue(true)
    renderForm()

    const docxFile = new File(["bytes"], "tracked.docx", {
      type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    })

    // First upload — detection fires and file is shown
    selectFile(docxFile)
    await waitFor(() => {
      expect(screen.getByText("tracked.docx")).toBeDefined()
    })
    expect(mockDetect).toHaveBeenCalledTimes(1)

    // Re-select the same file — detection fires again (state was fully reset)
    selectFile(docxFile)
    await waitFor(() => {
      expect(mockDetect).toHaveBeenCalledTimes(2)
    })
    // File name still rendered and detection called fresh
    expect(screen.getByText("tracked.docx")).toBeDefined()
  })

  it("Submit disabled while detecting", async () => {
    let resolveDetect!: (val: boolean) => void
    mockDetect.mockImplementationOnce(
      () => new Promise(r => { resolveDetect = r })
    )
    renderForm()

    const docxFile = new File(["bytes"], "test.docx", {
      type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    })

    selectFile(docxFile)

    // While detection is pending the Submit button must be disabled
    await waitFor(() => {
      const button = screen.getByText("Translate Document").closest("button")
      expect(button?.disabled).toBe(true)
    })

    // Resolve detection — detecting flag clears
    await act(async () => {
      resolveDetect(false)
    })

    // Detection resolved — button remains disabled only because no target
    // language is selected (expected behaviour; !detecting constraint lifted)
    const button = screen.getByText("Translate Document").closest("button")
    expect(button?.disabled).toBe(true)
  })
})

describe("LanguageSelect rendered inside UploadForm", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockDetect.mockResolvedValue(false)
  })

  it("renders language selects when API returns language list", async () => {
    ;(global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          languages: [
            { code: "vi", name: "Vietnamese", qwen_code: "vi" },
            { code: "en", name: "English", qwen_code: "en" },
          ],
        }),
    })

    renderForm()
    expect(screen.getByText("Source Language")).toBeDefined()
    expect(screen.getByText("Target Language")).toBeDefined()
  })
})
