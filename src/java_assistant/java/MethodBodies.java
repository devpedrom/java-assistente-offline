import com.sun.source.tree.ClassTree;
import com.sun.source.tree.CompilationUnitTree;
import com.sun.source.tree.MethodTree;
import com.sun.source.tree.Tree;
import com.sun.source.tree.VariableTree;
import com.sun.source.util.JavacTask;
import com.sun.source.util.SourcePositions;
import com.sun.source.util.Trees;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.Arrays;
import java.util.Base64;
import java.util.Locale;
import javax.tools.Diagnostic;
import javax.tools.DiagnosticCollector;
import javax.tools.JavaCompiler;
import javax.tools.JavaFileObject;
import javax.tools.StandardJavaFileManager;
import javax.tools.ToolProvider;

public class MethodBodies {
    private static String encoded(String value) {
        return Base64.getEncoder().encodeToString(value.getBytes(StandardCharsets.UTF_8));
    }

    public static void main(String[] args) throws Exception {
        if (args.length != 2) throw new IllegalArgumentException("source and owner required");
        String source = new String(Files.readAllBytes(Paths.get(args[0])), StandardCharsets.UTF_8);
        JavaCompiler compiler = ToolProvider.getSystemJavaCompiler();
        if (compiler == null) throw new IllegalStateException("JDK compiler unavailable");
        DiagnosticCollector<JavaFileObject> diagnostics = new DiagnosticCollector<>();
        StringBuilder output = new StringBuilder();
        try (StandardJavaFileManager files = compiler.getStandardFileManager(diagnostics, Locale.ROOT, StandardCharsets.UTF_8)) {
            JavacTask task = (JavacTask) compiler.getTask(null, files, diagnostics,
                Arrays.asList("-proc:none", "-source", "8", "-Xlint:none"), null,
                files.getJavaFileObjects(args[0]));
            SourcePositions positions = Trees.instance(task).getSourcePositions();
            for (CompilationUnitTree unit : task.parse()) {
                for (Tree declaration : unit.getTypeDecls()) {
                    if (!(declaration instanceof ClassTree)) continue;
                    ClassTree owner = (ClassTree) declaration;
                    if (!owner.getSimpleName().contentEquals(args[1])) continue;
                    for (Tree member : owner.getMembers()) {
                        if (!(member instanceof MethodTree)) continue;
                        MethodTree method = (MethodTree) member;
                        if (method.getReturnType() == null || method.getBody() == null) continue;
                        long start = positions.getStartPosition(unit, method.getBody());
                        long end = positions.getEndPosition(unit, method.getBody());
                        long declarationStart = positions.getStartPosition(unit, method);
                        StringBuilder parameters = new StringBuilder();
                        for (VariableTree parameter : method.getParameters()) {
                            if (parameters.length() > 0) parameters.append('\n');
                            parameters.append(parameter.getType().toString());
                        }
                        output.append(encoded(method.getName().toString())).append('\t')
                            .append(encoded(parameters.toString())).append('\t')
                            .append(start).append('\t').append(end).append('\t')
                            .append(encoded(source.substring((int) declarationStart, (int) start).trim())).append('\n');
                    }
                }
            }
            for (Diagnostic<?> diagnostic : diagnostics.getDiagnostics()) {
                if (diagnostic.getKind() == Diagnostic.Kind.ERROR)
                    throw new IllegalArgumentException(diagnostic.getMessage(Locale.ROOT));
            }
        }
        System.out.print(output);
    }
}
