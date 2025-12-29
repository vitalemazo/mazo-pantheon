try:
    from langchain_core.runnables.graph import MermaidDrawMethod
    VISUALIZE_AVAILABLE = True
except ImportError:
    VISUALIZE_AVAILABLE = False
    MermaidDrawMethod = None


def save_graph_as_png(app, output_file_path) -> None:
    """Save graph visualization as PNG. Requires langchain-core with graph support."""
    if not VISUALIZE_AVAILABLE:
        raise ImportError("Graph visualization requires langchain-core with graph support")
    
    try:
        png_image = app.get_graph().draw_mermaid_png(draw_method=MermaidDrawMethod.API)
        file_path = output_file_path if len(output_file_path) > 0 else "graph.png"
        with open(file_path, "wb") as f:
            f.write(png_image)
    except Exception as e:
        print(f"Warning: Could not generate graph visualization: {e}")
        print("Graph visualization is optional and can be skipped.")
