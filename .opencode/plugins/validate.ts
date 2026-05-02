import type { Plugin } from "@opencode-ai/plugin";

function trimBytes(buf: Uint8Array): string {
  return new TextDecoder().decode(buf).trimEnd();
}

function formatProcessBlock(
  title: string,
  exitCode: number,
  stdout: string,
  stderr: string,
): string {
  const parts = [
    "",
    "---",
    `[${title}] exit code: ${exitCode}`,
  ];
  if (stdout) parts.push("stdout:", stdout);
  if (stderr) parts.push("stderr:", stderr);
  if (!stdout && !stderr) parts.push("(no output)");
  return parts.join("\n");
}

export const ValidateHook: Plugin = async (pluginInput) => {
  const { $, directory } = pluginInput;
  const shell = $.cwd(directory);

  return {
    "tool.execute.after": async (hookInput, hookOutput) => {
      const tool = hookInput.tool?.toLowerCase() ?? "";
      if (!["write", "edit"].includes(tool)) return;

      const filePath = hookInput.args?.file_path ?? hookInput.args?.filePath;
      if (!filePath || typeof filePath !== "string") return;

      if (!filePath.includes("knowledge/articles") || !filePath.endsWith(".json")) {
        return;
      }

      const escapedPath = $.escape(filePath);
      const stamp = new Date().toISOString();

      console.log(`[validate-hook] ${stamp} 文章写入: ${filePath}`);

      const validateResult = await shell`python3 hooks/validate_json.py ${escapedPath}`
        .nothrow()
        .quiet();

      const vOut = trimBytes(validateResult.stdout);
      const vErr = trimBytes(validateResult.stderr);
      const jsonOk = validateResult.exitCode === 0;

      if (!jsonOk) {
        console.error(`[validate-hook] JSON 校验失败 (exit ${validateResult.exitCode})`);
        if (vOut) console.error(vOut);
        if (vErr) console.error(vErr);
      } else {
        console.log(`[validate-hook] JSON 校验通过`);
      }

      let qualityExit: number | null = null;
      let qOut = "";
      let qErr = "";
      let qualityOk: boolean | null = null;

      if (jsonOk) {
        const qualityResult = await shell`python3 hooks/check_quality.py ${escapedPath}`
          .nothrow()
          .quiet();
        qualityExit = qualityResult.exitCode;
        qOut = trimBytes(qualityResult.stdout);
        qErr = trimBytes(qualityResult.stderr);
        qualityOk = qualityResult.exitCode === 0;

        if (!qualityOk) {
          console.warn(`[validate-hook] 质量评分未达 B 级 (exit ${qualityResult.exitCode})`);
          if (qOut) console.warn(qOut);
          if (qErr) console.warn(qErr);
        } else {
          console.log(`[validate-hook] 质量评分达标 (B 级以上)`);
        }
      }

      const appendix = [
        "",
        "### 知识库校验（validate hook）",
        `- 文件: \`${filePath}\``,
        `- JSON 格式: ${jsonOk ? "通过" : "失败"}`,
        jsonOk
          ? `- 质量评分 (B+): ${qualityOk ? "通过" : "未达标（含 C 级）"}`
          : "- 质量评分: 已跳过（JSON 未通过）",
        formatProcessBlock("validate_json.py", validateResult.exitCode, vOut, vErr),
        jsonOk
          ? formatProcessBlock("check_quality.py", qualityExit ?? -1, qOut, qErr)
          : "",
      ]
        .filter(Boolean)
        .join("\n");

      hookOutput.output = `${hookOutput.output ?? ""}${appendix}`;

      const existingMetadata =
        hookOutput.metadata && typeof hookOutput.metadata === "object"
          ? hookOutput.metadata
          : {};

      hookOutput.metadata = {
        ...existingMetadata,
        validateHook: {
          at: stamp,
          filePath,
          jsonValidation: {
            exitCode: validateResult.exitCode,
            ok: jsonOk,
          },
          qualityCheck: jsonOk
            ? { exitCode: qualityExit, ok: qualityOk }
            : { skipped: true as const },
        },
      };
    },
  };
};

export const server = ValidateHook;
export default ValidateHook;
