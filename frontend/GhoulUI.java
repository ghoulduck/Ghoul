import javax.swing.*;
import javax.swing.border.*;
import javax.swing.text.*;
import java.awt.*;
import java.awt.event.*;
import java.io.*;
import java.nio.file.*;
import java.util.concurrent.*;

/**
 * GhoulUI — Java Swing desktop frontend for the Ghoul AI agent.
 *
 * Provides a graphical interface for all Ghoul CLI commands:
 *   Run, Improve, Collect, Fine-Tune, Orchestrate, Status, and History.
 *
 * Invokes `python main.py` (or a bundled ghoul executable, or a configurable
 * interpreter/script path) as a subprocess and streams output live into the
 * output panel.
 *
 * Compile & run:
 *   javac GhoulUI.java
 *   java GhoulUI
 *
 * Or use the provided run.sh script.
 */
public class GhoulUI extends JFrame {

    // -----------------------------------------------------------------------
    // Constants
    // -----------------------------------------------------------------------

    private static final String APP_TITLE = "Ghoul — Self-Improving AI Agent";
    private static final Color BG_DARK    = new Color(18, 18, 24);
    private static final Color BG_PANEL   = new Color(28, 28, 38);
    private static final Color BG_INPUT   = new Color(38, 38, 52);
    private static final Color FG_TEXT    = new Color(220, 220, 235);
    private static final Color FG_DIM     = new Color(140, 140, 160);
    private static final Color ACCENT     = new Color(138, 91, 246);   // purple
    private static final Color ACCENT_HOV = new Color(160, 115, 255);
    private static final Color SUCCESS    = new Color(72, 199, 142);
    private static final Color ERROR_COL  = new Color(240, 80, 80);
    private static final Font  MONO_FONT  = new Font(Font.MONOSPACED, Font.PLAIN, 13);
    private static final Font  UI_FONT    = new Font(Font.SANS_SERIF,  Font.PLAIN, 13);
    private static final Font  TITLE_FONT = new Font(Font.SANS_SERIF,  Font.BOLD,  20);

    // -----------------------------------------------------------------------
    // State
    // -----------------------------------------------------------------------

    /** Working directory — where main.py lives (parent of frontend/). */
    private File workingDir;
    /** Python interpreter path. */
    private String pythonExe = "python";
    /** Whether a bundled ghoul/ghoul.exe was found next to the class file. */
    private boolean useBundledExe;
    /** Absolute path to the bundled executable (set when useBundledExe is true). */
    private String bundledExePath;
    /** Currently running subprocess. */
    private volatile Process activeProcess;
    /** Executor for background subprocess threads. */
    private final ExecutorService executor = Executors.newCachedThreadPool();

    // -----------------------------------------------------------------------
    // UI components
    // -----------------------------------------------------------------------

    private JTextPane  outputPane;
    private JTextField taskField;
    private JTextField topicField;
    private JTextField urlsField;
    private JTextField githubQueryField;
    private JSpinner   syntheticCountSpinner;
    private JTextField dataPathField;
    private JComboBox<String> ftTargetCombo;
    private JTextField moduleField;
    private JTextField instructionsField;
    private JTextField sessionIdField;
    private JTextField pythonPathField;
    private JButton    stopButton;
    private JLabel     statusLabel;
    private JTabbedPane tabs;

    // Orchestrate tab fields
    private JTextField orchModulesField;
    private JTextField orchSpecialistsField;
    private JTextField orchInstructionsField;

    // History tab
    private JTextArea  historyArea;

    // -----------------------------------------------------------------------
    // Entry point
    // -----------------------------------------------------------------------

    public static void main(String[] args) {
        SwingUtilities.invokeLater(() -> {
            try {
                UIManager.setLookAndFeel(UIManager.getSystemLookAndFeelClassName());
            } catch (Exception ignored) {}
            new GhoulUI().setVisible(true);
        });
    }

    // -----------------------------------------------------------------------
    // Constructor
    // -----------------------------------------------------------------------

    public GhoulUI() {
        super(APP_TITLE);
        workingDir = detectWorkingDir();
        buildUI();
        setSize(1100, 780);
        setMinimumSize(new Dimension(800, 580));
        setDefaultCloseOperation(JFrame.EXIT_ON_CLOSE);
        setLocationRelativeTo(null);
        String readyMsg = "Ghoul UI ready. Working directory: " + workingDir.getAbsolutePath();
        if (useBundledExe) readyMsg += "  [bundled exe: " + bundledExePath + "]";
        appendOutput(readyMsg + "\n", FG_DIM);
    }

    // -----------------------------------------------------------------------
    // Working-directory detection
    // -----------------------------------------------------------------------

    /**
     * Try to locate the Ghoul project root (the folder that contains main.py).
     * Also checks for a bundled ghoul / ghoul.exe executable.
     * Falls back to the current working directory.
     */
    private File detectWorkingDir() {
        // If this JAR/class lives inside frontend/, go up one level.
        try {
            File classDir = new File(
                GhoulUI.class.getProtectionDomain().getCodeSource().getLocation().toURI()
            );
            File parent = classDir.isFile() ? classDir.getParentFile() : classDir;
            // If we're in frontend/, step up
            if (parent.getName().equals("frontend")) {
                File up = parent.getParentFile();
                if (new File(up, "main.py").exists()) {
                    checkBundledExe(up);
                    return up;
                }
            }
            // Maybe main.py is right here
            if (new File(parent, "main.py").exists()) {
                checkBundledExe(parent);
                return parent;
            }
            // No main.py found — still check for bundled exe
            checkBundledExe(parent);
            if (useBundledExe) return parent;
        } catch (Exception ignored) {}
        File cwd = new File(System.getProperty("user.dir"));
        checkBundledExe(cwd);
        return cwd;
    }

    /**
     * Look for a bundled ghoul or ghoul.exe executable in the given directory.
     * If found and executable, set {@link #useBundledExe} and {@link #bundledExePath}.
     */
    private void checkBundledExe(File dir) {
        if (useBundledExe) return; // already found
        File ghoulExe = new File(dir, "ghoul.exe");
        if (ghoulExe.exists() && ghoulExe.canExecute()) {
            useBundledExe = true;
            bundledExePath = ghoulExe.getAbsolutePath();
            return;
        }
        File ghoul = new File(dir, "ghoul");
        if (ghoul.exists() && ghoul.canExecute()) {
            useBundledExe = true;
            bundledExePath = ghoul.getAbsolutePath();
        }
    }

    // -----------------------------------------------------------------------
    // UI construction
    // -----------------------------------------------------------------------

    private void buildUI() {
        getContentPane().setBackground(BG_DARK);
        setLayout(new BorderLayout(0, 0));

        add(buildHeader(),  BorderLayout.NORTH);
        add(buildCenter(),  BorderLayout.CENTER);
        add(buildStatusBar(), BorderLayout.SOUTH);
    }

    // --- Header ---

    private JPanel buildHeader() {
        JPanel header = new JPanel(new BorderLayout());
        header.setBackground(BG_PANEL);
        header.setBorder(new EmptyBorder(12, 18, 12, 18));

        JLabel title = new JLabel("👻 Ghoul");
        title.setFont(TITLE_FONT);
        title.setForeground(ACCENT);
        header.add(title, BorderLayout.WEST);

        JLabel sub = new JLabel("Self-Improving AI Agent · Powered by Anthropic Claude");
        sub.setFont(UI_FONT);
        sub.setForeground(FG_DIM);
        header.add(sub, BorderLayout.CENTER);

        // Session ID + Python path (top-right)
        JPanel rightPanel = new JPanel(new FlowLayout(FlowLayout.RIGHT, 8, 0));
        rightPanel.setBackground(BG_PANEL);

        rightPanel.add(dim("Session ID:"));
        sessionIdField = styledField("", 14);
        sessionIdField.setToolTipText("Leave blank to start a new session, or enter an ID to resume one.");
        rightPanel.add(sessionIdField);

        rightPanel.add(dim("Python:"));
        pythonPathField = styledField("python", 10);
        pythonPathField.setToolTipText("Python interpreter command or path (e.g. python3, /usr/bin/python3).");
        pythonPathField.addActionListener(e -> pythonExe = pythonPathField.getText().trim());
        rightPanel.add(pythonPathField);

        header.add(rightPanel, BorderLayout.EAST);
        return header;
    }

    // --- Center split: tabs (left) + output (right) ---

    private JSplitPane buildCenter() {
        tabs = buildTabs();
        JPanel outputPanel = buildOutputPanel();

        JSplitPane split = new JSplitPane(JSplitPane.HORIZONTAL_SPLIT, tabs, outputPanel);
        split.setDividerLocation(420);
        split.setDividerSize(4);
        split.setBackground(BG_DARK);
        split.setBorder(null);
        return split;
    }

    // --- Tabbed command panels ---

    private JTabbedPane buildTabs() {
        tabs = new JTabbedPane(JTabbedPane.TOP);
        tabs.setBackground(BG_PANEL);
        tabs.setForeground(FG_TEXT);
        tabs.setFont(UI_FONT);

        tabs.addTab("▶  Run",         buildRunPanel());
        tabs.addTab("⚙  Improve",     buildImprovePanel());
        tabs.addTab("📦 Collect",     buildCollectPanel());
        tabs.addTab("🎛  Fine-Tune",   buildFineTunePanel());
        tabs.addTab("🔀 Orchestrate", buildOrchestratePanel());
        tabs.addTab("📊 Status",      buildStatusPanel());
        tabs.addTab("📜 History",     buildHistoryPanel());
        tabs.addTab("⚙  Settings",    buildSettingsPanel());

        return tabs;
    }

    // Run tab
    private JPanel buildRunPanel() {
        JPanel p = tabPanel("Run the agent on a task");

        taskField = styledField("e.g. Write a Python function to compute Fibonacci numbers", 30);
        addFormRow(p, "Task:", taskField, true);

        p.add(Box.createVerticalStrut(16));

        JButton runBtn = accentButton("▶  Run Agent");
        runBtn.addActionListener(e -> runCommand("run", buildRunArgs()));
        p.add(btnRow(runBtn));

        padBottom(p);
        return p;
    }

    private String[] buildRunArgs() {
        String task = getFieldValue(taskField);
        if (task.isEmpty()) { showError("Please enter a task."); return null; }
        return new String[]{ task };
    }

    // Improve tab
    private JPanel buildImprovePanel() {
        JPanel p = tabPanel("Ask Claude to improve Ghoul's own source code");

        moduleField = styledField("Leave blank to improve all modules", 30);
        moduleField.setToolTipText("Space-separated module names, e.g.: executor evaluator");
        addFormRow(p, "Modules:", moduleField, true);

        instructionsField = styledField("Optional specific instructions for Claude", 30);
        addFormRow(p, "Instructions:", instructionsField, true);

        p.add(Box.createVerticalStrut(16));

        JButton improveBtn = accentButton("⚙  Improve Code");
        improveBtn.addActionListener(e -> runCommand("improve", buildImproveArgs()));
        JPanel btnRow = btnRow(improveBtn);
        p.add(btnRow);

        padBottom(p);
        return p;
    }

    private String[] buildImproveArgs() {
        String modules = getFieldValue(moduleField);
        String instructions = getFieldValue(instructionsField);
        java.util.List<String> args = new java.util.ArrayList<>();
        if (!modules.isEmpty()) {
            for (String m : modules.split("\\s+")) args.add(m);
        }
        if (!instructions.isEmpty()) {
            args.add("--instructions");
            args.add(instructions);
        }
        return args.toArray(new String[0]);
    }

    // Collect tab
    private JPanel buildCollectPanel() {
        JPanel p = tabPanel("Collect training data from web, GitHub, and Claude");

        topicField = styledField("e.g. Python sorting algorithms", 30);
        addFormRow(p, "Topic:", topicField, true);

        urlsField = styledField("Space-separated URLs to scrape (optional)", 30);
        addFormRow(p, "URLs:", urlsField, false);

        githubQueryField = styledField("GitHub search query override (optional)", 30);
        addFormRow(p, "GitHub Query:", githubQueryField, false);

        syntheticCountSpinner = new JSpinner(new SpinnerNumberModel(10, 1, 200, 1));
        syntheticCountSpinner.setBackground(BG_INPUT);
        syntheticCountSpinner.setForeground(FG_TEXT);
        JPanel spinRow = new JPanel(new FlowLayout(FlowLayout.LEFT, 0, 0));
        spinRow.setBackground(BG_PANEL);
        spinRow.add(syntheticCountSpinner);
        addFormRow(p, "Synthetic Count:", spinRow, false);

        p.add(Box.createVerticalStrut(16));

        JButton collectBtn = accentButton("📦 Collect Data");
        collectBtn.addActionListener(e -> runCommand("collect", buildCollectArgs()));
        p.add(btnRow(collectBtn));

        padBottom(p);
        return p;
    }

    private String[] buildCollectArgs() {
        String topic = getFieldValue(topicField);
        if (topic.isEmpty()) { showError("Please enter a topic."); return null; }
        java.util.List<String> args = new java.util.ArrayList<>();
        args.add(topic);
        String urls = getFieldValue(urlsField);
        if (!urls.isEmpty()) {
            args.add("--urls");
            for (String u : urls.split("\\s+")) args.add(u);
        }
        String ghQ = getFieldValue(githubQueryField);
        if (!ghQ.isEmpty()) {
            args.add("--github-query");
            args.add(ghQ);
        }
        int count = (Integer) syntheticCountSpinner.getValue();
        args.add("--synthetic-count");
        args.add(String.valueOf(count));
        return args.toArray(new String[0]);
    }

    // Fine-Tune tab
    private JPanel buildFineTunePanel() {
        JPanel p = tabPanel("Run the fine-tuning pipeline on collected data");

        dataPathField = styledField("Path to training JSONL file", 30);
        JButton browseBtn = new JButton("Browse…");
        browseBtn.setBackground(BG_INPUT);
        browseBtn.setForeground(FG_TEXT);
        browseBtn.addActionListener(e -> {
            JFileChooser fc = new JFileChooser(workingDir);
            fc.setDialogTitle("Select training data JSONL file");
            if (fc.showOpenDialog(this) == JFileChooser.APPROVE_OPTION) {
                dataPathField.setText(fc.getSelectedFile().getAbsolutePath());
            }
        });
        JPanel dataRow = new JPanel(new BorderLayout(6, 0));
        dataRow.setBackground(BG_PANEL);
        dataRow.add(dataPathField, BorderLayout.CENTER);
        dataRow.add(browseBtn, BorderLayout.EAST);
        addFormRow(p, "Data File:", dataRow, true);

        ftTargetCombo = new JComboBox<>(new String[]{ "anthropic", "huggingface" });
        ftTargetCombo.setBackground(BG_INPUT);
        ftTargetCombo.setForeground(FG_TEXT);
        addFormRow(p, "Target:", ftTargetCombo, false);

        p.add(Box.createVerticalStrut(16));

        JButton ftBtn = accentButton("🎛  Start Fine-Tuning");
        ftBtn.addActionListener(e -> runCommand("fine-tune", buildFineTuneArgs()));
        p.add(btnRow(ftBtn));

        padBottom(p);
        return p;
    }

    private String[] buildFineTuneArgs() {
        String path = getFieldValue(dataPathField);
        if (path.isEmpty()) { showError("Please specify a data file path."); return null; }
        String target = (String) ftTargetCombo.getSelectedItem();
        return new String[]{ path, "--target", target };
    }

    // Orchestrate tab
    private JPanel buildOrchestratePanel() {
        JPanel p = tabPanel("Orchestrate multi-module agent workflows");

        orchModulesField = styledField("Space-separated module names (blank = all)", 30);
        orchModulesField.setToolTipText("Module names to orchestrate, e.g.: executor evaluator. Leave blank for all.");
        addFormRow(p, "Modules:", orchModulesField, false);

        orchSpecialistsField = styledField("Comma-separated specialist IDs (blank = all)", 30);
        orchSpecialistsField.setToolTipText("Specialist IDs to use, e.g.: spec1,spec2. Leave blank for all.");
        addFormRow(p, "Specialists:", orchSpecialistsField, false);

        orchInstructionsField = styledField("Extra instructions for orchestration", 30);
        addFormRow(p, "Instructions:", orchInstructionsField, false);

        p.add(Box.createVerticalStrut(16));

        JButton orchBtn = accentButton("🔀 Orchestrate");
        orchBtn.addActionListener(e -> runCommand("orchestrate", buildOrchestrateArgs()));
        p.add(btnRow(orchBtn));

        padBottom(p);
        return p;
    }

    private String[] buildOrchestrateArgs() {
        java.util.List<String> args = new java.util.ArrayList<>();
        String modules = getFieldValue(orchModulesField);
        if (!modules.isEmpty()) {
            for (String m : modules.split("\\s+")) args.add(m);
        }
        String specialists = getFieldValue(orchSpecialistsField);
        if (!specialists.isEmpty()) {
            args.add("--specialists");
            args.add(specialists);
        }
        String instr = getFieldValue(orchInstructionsField);
        if (!instr.isEmpty()) {
            args.add("--instructions");
            args.add(instr);
        }
        return args.toArray(new String[0]);
    }

    // Status tab
    private JPanel buildStatusPanel() {
        JPanel p = tabPanel("View agent history and metrics");
        p.add(Box.createVerticalStrut(10));
        JButton statusBtn = accentButton("📊 Show Status");
        statusBtn.addActionListener(e -> runCommand("status", new String[0]));
        p.add(btnRow(statusBtn));
        padBottom(p);
        return p;
    }

    // History tab
    private JPanel buildHistoryPanel() {
        JPanel p = new JPanel(new BorderLayout(0, 10));
        p.setBackground(BG_PANEL);
        p.setBorder(new EmptyBorder(18, 18, 18, 18));

        // Top section: description + refresh button
        JPanel top = new JPanel();
        top.setBackground(BG_PANEL);
        top.setLayout(new BoxLayout(top, BoxLayout.Y_AXIS));

        JLabel desc = new JLabel("View detailed session history");
        desc.setForeground(FG_DIM);
        desc.setFont(new Font(Font.SANS_SERIF, Font.ITALIC, 12));
        desc.setAlignmentX(Component.LEFT_ALIGNMENT);
        top.add(desc);
        top.add(Box.createVerticalStrut(14));

        JButton refreshBtn = accentButton("🔄 Refresh");
        refreshBtn.addActionListener(e -> refreshHistory());
        JPanel refreshRow = btnRow(refreshBtn);
        top.add(refreshRow);

        p.add(top, BorderLayout.NORTH);

        // Scrollable text area for history output
        historyArea = new JTextArea();
        historyArea.setEditable(false);
        historyArea.setBackground(BG_DARK);
        historyArea.setForeground(FG_TEXT);
        historyArea.setFont(MONO_FONT);
        historyArea.setBorder(new EmptyBorder(8, 8, 8, 8));
        historyArea.setLineWrap(true);
        historyArea.setWrapStyleWord(true);

        JScrollPane scroll = new JScrollPane(historyArea);
        scroll.setBorder(BorderFactory.createLineBorder(BG_INPUT, 1));
        scroll.getViewport().setBackground(BG_DARK);

        p.add(scroll, BorderLayout.CENTER);
        return p;
    }

    /** Run `status` in the background and display output in the History text area. */
    private void refreshHistory() {
        historyArea.setText("Loading…\n");

        java.util.List<String> cmd = buildBaseCommand();
        cmd.add("status");

        executor.submit(() -> {
            try {
                ProcessBuilder pb = new ProcessBuilder(cmd);
                pb.directory(workingDir);
                pb.redirectErrorStream(true);
                Process proc = pb.start();

                StringBuilder sb = new StringBuilder();
                try (BufferedReader reader = new BufferedReader(
                        new InputStreamReader(proc.getInputStream()))) {
                    String line;
                    while ((line = reader.readLine()) != null) {
                        sb.append(line).append("\n");
                    }
                }
                proc.waitFor();
                SwingUtilities.invokeLater(() -> {
                    historyArea.setText(sb.toString());
                    historyArea.setCaretPosition(0);
                });
            } catch (Exception ex) {
                SwingUtilities.invokeLater(() ->
                    historyArea.setText("Error: " + ex.getMessage() + "\n"));
            }
        });
    }

    // Settings tab
    private JPanel buildSettingsPanel() {
        JPanel p = tabPanel("Configure Ghoul settings");

        JTextField wdField = styledField(workingDir.getAbsolutePath(), 30);
        JButton wdBrowse = new JButton("Browse…");
        wdBrowse.setBackground(BG_INPUT);
        wdBrowse.setForeground(FG_TEXT);
        wdBrowse.addActionListener(e -> {
            JFileChooser fc = new JFileChooser(workingDir);
            fc.setFileSelectionMode(JFileChooser.DIRECTORIES_ONLY);
            fc.setDialogTitle("Select Ghoul project root (where main.py lives)");
            if (fc.showOpenDialog(this) == JFileChooser.APPROVE_OPTION) {
                workingDir = fc.getSelectedFile();
                wdField.setText(workingDir.getAbsolutePath());
                appendOutput("Working directory set to: " + workingDir.getAbsolutePath() + "\n", SUCCESS);
            }
        });
        JPanel wdRow = new JPanel(new BorderLayout(6, 0));
        wdRow.setBackground(BG_PANEL);
        wdRow.add(wdField, BorderLayout.CENTER);
        wdRow.add(wdBrowse, BorderLayout.EAST);
        addFormRow(p, "Project Root:", wdRow, true);

        JLabel note = dim("Set ANTHROPIC_API_KEY and other variables in your shell environment\n"
            + "or in a config.yaml file in the project root before launching Ghoul.");
        note.setFont(UI_FONT);
        p.add(Box.createVerticalStrut(10));
        p.add(note);

        padBottom(p);
        return p;
    }

    // --- Output panel ---

    private JPanel buildOutputPanel() {
        outputPane = new JTextPane();
        outputPane.setEditable(false);
        outputPane.setBackground(BG_DARK);
        outputPane.setForeground(FG_TEXT);
        outputPane.setFont(MONO_FONT);
        outputPane.setBorder(new EmptyBorder(10, 12, 10, 12));

        JScrollPane scroll = new JScrollPane(outputPane);
        scroll.setBorder(BorderFactory.createLineBorder(BG_PANEL, 1));
        scroll.getViewport().setBackground(BG_DARK);

        JButton clearBtn = new JButton("Clear");
        clearBtn.setBackground(BG_INPUT);
        clearBtn.setForeground(FG_DIM);
        clearBtn.setFont(UI_FONT);
        clearBtn.setBorder(new EmptyBorder(4, 10, 4, 10));
        clearBtn.addActionListener(e -> outputPane.setText(""));

        JPanel topBar = new JPanel(new BorderLayout());
        topBar.setBackground(BG_PANEL);
        topBar.setBorder(new EmptyBorder(6, 12, 6, 12));
        JLabel outLabel = new JLabel("Output");
        outLabel.setForeground(FG_TEXT);
        outLabel.setFont(new Font(Font.SANS_SERIF, Font.BOLD, 13));
        topBar.add(outLabel, BorderLayout.WEST);
        topBar.add(clearBtn, BorderLayout.EAST);

        JPanel panel = new JPanel(new BorderLayout());
        panel.setBackground(BG_DARK);
        panel.add(topBar, BorderLayout.NORTH);
        panel.add(scroll, BorderLayout.CENTER);
        return panel;
    }

    // --- Status bar ---

    private JPanel buildStatusBar() {
        JPanel bar = new JPanel(new BorderLayout());
        bar.setBackground(BG_PANEL);
        bar.setBorder(new EmptyBorder(5, 12, 5, 12));

        statusLabel = new JLabel("Ready");
        statusLabel.setFont(UI_FONT);
        statusLabel.setForeground(FG_DIM);
        bar.add(statusLabel, BorderLayout.WEST);

        stopButton = new JButton("■ Stop");
        stopButton.setBackground(ERROR_COL);
        stopButton.setForeground(Color.WHITE);
        stopButton.setFont(new Font(Font.SANS_SERIF, Font.BOLD, 12));
        stopButton.setBorder(new EmptyBorder(4, 12, 4, 12));
        stopButton.setEnabled(false);
        stopButton.addActionListener(e -> stopActiveProcess());
        bar.add(stopButton, BorderLayout.EAST);

        return bar;
    }

    // -----------------------------------------------------------------------
    // Process execution
    // -----------------------------------------------------------------------

    /**
     * Build the base command prefix: either the bundled executable or
     * python + main.py.
     */
    private java.util.List<String> buildBaseCommand() {
        java.util.List<String> cmd = new java.util.ArrayList<>();
        if (useBundledExe && bundledExePath != null) {
            cmd.add(bundledExePath);
        } else {
            pythonExe = pythonPathField.getText().trim();
            if (pythonExe.isEmpty()) pythonExe = "python";
            cmd.add(pythonExe);
            cmd.add("main.py");
        }
        return cmd;
    }

    /**
     * Build the full command array and run it in a background thread.
     *
     * @param subcommand  The Ghoul subcommand (e.g. "run", "improve").
     * @param extraArgs   Additional arguments for that subcommand (may be null).
     */
    private void runCommand(String subcommand, String[] extraArgs) {
        if (extraArgs == null) return;  // validation already showed an error dialog

        java.util.List<String> cmd = buildBaseCommand();

        String sid = getFieldValue(sessionIdField);
        if (!sid.isEmpty()) {
            cmd.add("--session-id");
            cmd.add(sid);
        }

        cmd.add(subcommand);
        for (String a : extraArgs) cmd.add(a);

        String displayCmd = String.join(" ", cmd);
        appendOutput("\n$ " + displayCmd + "\n", ACCENT);
        setStatus("Running: " + subcommand + "…", ACCENT);
        stopButton.setEnabled(true);

        executor.submit(() -> {
            try {
                ProcessBuilder pb = new ProcessBuilder(cmd);
                pb.directory(workingDir);
                pb.redirectErrorStream(true);   // merge stderr into stdout
                activeProcess = pb.start();

                try (BufferedReader reader = new BufferedReader(
                        new InputStreamReader(activeProcess.getInputStream()))) {
                    String line;
                    while ((line = reader.readLine()) != null) {
                        final String l = line;
                        SwingUtilities.invokeLater(() -> appendOutput(l + "\n", FG_TEXT));
                    }
                }

                int rc = activeProcess.waitFor();
                final Color col = rc == 0 ? SUCCESS : ERROR_COL;
                final String msg = rc == 0
                    ? "✓ Process exited successfully (rc=0)\n"
                    : "✗ Process exited with code " + rc + "\n";
                SwingUtilities.invokeLater(() -> {
                    appendOutput(msg, col);
                    setStatus("Done (rc=" + rc + ")", col);
                    stopButton.setEnabled(false);
                });
            } catch (Exception ex) {
                SwingUtilities.invokeLater(() -> {
                    appendOutput("Error: " + ex.getMessage() + "\n", ERROR_COL);
                    setStatus("Error", ERROR_COL);
                    stopButton.setEnabled(false);
                });
            } finally {
                activeProcess = null;
            }
        });
    }

    private void stopActiveProcess() {
        Process p = activeProcess;
        if (p != null && p.isAlive()) {
            p.destroyForcibly();
            appendOutput("\n[Process stopped by user]\n", ERROR_COL);
            setStatus("Stopped", ERROR_COL);
        }
        stopButton.setEnabled(false);
    }

    // -----------------------------------------------------------------------
    // Output helpers
    // -----------------------------------------------------------------------

    private void appendOutput(String text, Color color) {
        StyledDocument doc = outputPane.getStyledDocument();
        Style style = outputPane.addStyle("colored", null);
        StyleConstants.setForeground(style, color);
        StyleConstants.setFontFamily(style, Font.MONOSPACED);
        StyleConstants.setFontSize(style, 13);
        try {
            doc.insertString(doc.getLength(), text, style);
        } catch (BadLocationException ignored) {}
        // Auto-scroll to bottom
        outputPane.setCaretPosition(doc.getLength());
    }

    private void setStatus(String text, Color color) {
        statusLabel.setText(text);
        statusLabel.setForeground(color);
    }

    private void showError(String msg) {
        JOptionPane.showMessageDialog(this, msg, "Input Error", JOptionPane.ERROR_MESSAGE);
    }

    // -----------------------------------------------------------------------
    // Widget factories
    // -----------------------------------------------------------------------

    /** Styled single-line text field with placeholder behaviour. */
    private JTextField styledField(String placeholder, int cols) {
        JTextField f = new JTextField(cols);
        f.setBackground(BG_INPUT);
        f.setForeground(FG_TEXT);
        f.setCaretColor(FG_TEXT);
        f.setFont(UI_FONT);
        f.setBorder(BorderFactory.createCompoundBorder(
            BorderFactory.createLineBorder(ACCENT.darker(), 1),
            new EmptyBorder(4, 8, 4, 8)
        ));
        f.setToolTipText(placeholder);
        // Store placeholder so getFieldValue can distinguish it from real input
        f.putClientProperty("placeholder", placeholder);
        // Show placeholder text
        f.addFocusListener(new FocusAdapter() {
            @Override public void focusGained(FocusEvent e) {
                if (f.getText().equals(placeholder)) { f.setText(""); f.setForeground(FG_TEXT); }
            }
            @Override public void focusLost(FocusEvent e) {
                if (f.getText().isEmpty()) { f.setText(placeholder); f.setForeground(FG_DIM); }
            }
        });
        f.setText(placeholder);
        f.setForeground(FG_DIM);
        return f;
    }

    /**
     * Return the real user-entered value from a styled field, or empty string
     * if the field still shows its placeholder text.
     */
    private String getFieldValue(JTextField field, String placeholder) {
        String text = field.getText().trim();
        if (text.equals(placeholder) && field.getForeground().equals(FG_DIM)) return "";
        return text;
    }

    /** Convenience overload that reads the placeholder from the field's client property. */
    private String getFieldValue(JTextField field) {
        String placeholder = (String) field.getClientProperty("placeholder");
        return getFieldValue(field, placeholder != null ? placeholder : "");
    }

    private JButton accentButton(String label) {
        JButton btn = new JButton(label);
        btn.setBackground(ACCENT);
        btn.setForeground(Color.WHITE);
        btn.setFont(new Font(Font.SANS_SERIF, Font.BOLD, 13));
        btn.setBorder(new EmptyBorder(8, 18, 8, 18));
        btn.setFocusPainted(false);
        btn.setCursor(Cursor.getPredefinedCursor(Cursor.HAND_CURSOR));
        btn.addMouseListener(new MouseAdapter() {
            @Override public void mouseEntered(MouseEvent e) { btn.setBackground(ACCENT_HOV); }
            @Override public void mouseExited(MouseEvent e)  { btn.setBackground(ACCENT); }
        });
        return btn;
    }

    private JLabel dim(String text) {
        JLabel lbl = new JLabel("<html>" + text.replace("\n", "<br>") + "</html>");
        lbl.setForeground(FG_DIM);
        lbl.setFont(UI_FONT);
        return lbl;
    }

    /** Tab content panel with a title label. */
    private JPanel tabPanel(String description) {
        JPanel p = new JPanel();
        p.setBackground(BG_PANEL);
        p.setLayout(new BoxLayout(p, BoxLayout.Y_AXIS));
        p.setBorder(new EmptyBorder(18, 18, 18, 18));

        JLabel desc = new JLabel(description);
        desc.setForeground(FG_DIM);
        desc.setFont(new Font(Font.SANS_SERIF, Font.ITALIC, 12));
        desc.setAlignmentX(Component.LEFT_ALIGNMENT);
        p.add(desc);
        p.add(Box.createVerticalStrut(14));
        return p;
    }

    /** Add a label + component row to a BoxLayout panel. */
    private void addFormRow(JPanel parent, String labelText, JComponent field, boolean required) {
        JLabel label = new JLabel(labelText + (required ? " *" : ""));
        label.setForeground(required ? FG_TEXT : FG_DIM);
        label.setFont(new Font(Font.SANS_SERIF, Font.BOLD, 12));
        label.setAlignmentX(Component.LEFT_ALIGNMENT);

        field.setAlignmentX(Component.LEFT_ALIGNMENT);
        if (field instanceof JTextField) {
            ((JTextField) field).setMaximumSize(new Dimension(Integer.MAX_VALUE, 34));
        }

        parent.add(label);
        parent.add(Box.createVerticalStrut(4));
        parent.add(field);
        parent.add(Box.createVerticalStrut(12));
    }

    /** Button row panel. */
    private JPanel btnRow(JButton... btns) {
        JPanel row = new JPanel(new FlowLayout(FlowLayout.LEFT, 0, 0));
        row.setBackground(BG_PANEL);
        row.setAlignmentX(Component.LEFT_ALIGNMENT);
        for (JButton b : btns) {
            row.add(b);
            row.add(Box.createHorizontalStrut(10));
        }
        return row;
    }

    private void padBottom(JPanel p) {
        p.add(Box.createVerticalGlue());
    }
}
