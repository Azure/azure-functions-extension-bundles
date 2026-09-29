using Colors.Net;
using Colors.Net.StringColorExtensions;
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Text;

namespace Build
{
    public static class Shell
    {
        public static void Run(string program, IReadOnlyList<string> arguments, bool streamOutput = true, bool silent = false)
        {
            var exe = new InternalExe(program, arguments, streamOutput);

            if (!silent)
            {
                ColoredConsole.WriteLine($"> {program} {FormatArguments(arguments)}".Green());
            }

            var exitcode = silent
                ? exe.Run()
                : exe.Run(l => ColoredConsole.Out.WriteLine(l.DarkGray()), e => ColoredConsole.Error.WriteLine(e.Red()));

            if (exitcode != 0)
            {
                throw new Exception($"{program} Exit Code == {exitcode}");
            }
        }

        public static string GetOutput(string program, IReadOnlyList<string> arguments, bool ignoreExitCode = false)
        {
            var exe = new InternalExe(program, arguments);
            var sb = new StringBuilder();
            var exitCode = exe.Run(o => sb.AppendLine(o?.Trim()), e => ColoredConsole.Error.WriteLine(e.Red()));

            if (!ignoreExitCode && exitCode != 0)
            {
                throw new Exception($"{program} exit code == {exitCode}");
            }

            return sb.ToString().Trim(new[] { ' ', '\r', '\n' });
        }

        private static string FormatArguments(IEnumerable<string> arguments)
        {
            return string.Join(" ", arguments.Select(argument =>
                argument.Any(char.IsWhiteSpace) ? $"\"{argument.Replace("\"", "\\\"")}\"" : argument));
        }

        class InternalExe
        {
            private readonly IReadOnlyList<string> _arguments;
            private readonly string _exeName;
            private readonly bool _shareConsole;
            private readonly bool _streamOutput;
            private readonly bool _visibleProcess;

            public InternalExe(string exeName, IReadOnlyList<string> arguments, bool streamOutput = true, bool shareConsole = false, bool visibleProcess = false)
            {
                _exeName = exeName;
                _arguments = arguments ?? Array.Empty<string>();
                _streamOutput = streamOutput;
                _shareConsole = shareConsole;
                _visibleProcess = visibleProcess;
            }

            public int Run(Action<string> outputCallback = null, Action<string> errorCallback = null)
            {
                var processInfo = new ProcessStartInfo
                {
                    FileName = _exeName,
                    CreateNoWindow = !_visibleProcess,
                    UseShellExecute = _shareConsole,
                    RedirectStandardError = _streamOutput,
                    RedirectStandardInput = _streamOutput,
                    RedirectStandardOutput = _streamOutput,
                    WorkingDirectory = Directory.GetCurrentDirectory()
                };

                foreach (var argument in _arguments)
                {
                    processInfo.ArgumentList.Add(argument);
                }

                Process process = null;

                try
                {
                    process = Process.Start(processInfo);
                }
                catch (Win32Exception ex)
                {
                    if (ex.Message == "The system cannot find the file specified")
                    {
                        throw new FileNotFoundException(ex.Message, ex);
                    }

                    throw;
                }

                if (_streamOutput)
                {
                    if (outputCallback != null)
                    {
                        process.OutputDataReceived += (s, e) =>
                        {
                            if (e.Data != null)
                            {
                                outputCallback(e.Data);
                            }
                        };
                        process.BeginOutputReadLine();
                    }

                    if (errorCallback != null)
                    {
                        process.ErrorDataReceived += (s, e) =>
                        {
                            if (!string.IsNullOrWhiteSpace(e.Data))
                            {
                                errorCallback(e.Data);
                            }
                        };
                        process.BeginErrorReadLine();
                    }
                    process.EnableRaisingEvents = true;
                }
                process.WaitForExit();
                return process.ExitCode;
            }
        }
    }
}