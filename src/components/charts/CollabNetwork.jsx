import * as d3 from "d3";
import { useEffect, useRef } from "react";

export function CollabNetwork({ tracks = [] }) {
  const ref = useRef(null);

  useEffect(() => {
    const collabs = tracks.filter((track) => track.is_collaboration || track.performer_role === "featured");
    const root = d3.select(ref.current);
    root.selectAll("*").remove();

    if (collabs.length < 2) return undefined;

    const width = ref.current.clientWidth || 700;
    const height = 420;
    const nodesById = new Map();
    const links = [];

    for (const track of collabs) {
      const followed = track.artist_name || "Followed artist";
      const partners = (track.all_artists || []).filter((artist) => artist !== followed);
      if (!nodesById.has(followed)) nodesById.set(followed, { id: followed, followed: true, count: 0 });
      nodesById.get(followed).count += 1;
      for (const partner of partners.slice(0, 3)) {
        if (!nodesById.has(partner)) nodesById.set(partner, { id: partner, followed: false, count: 0 });
        nodesById.get(partner).count += 1;
        links.push({ source: followed, target: partner });
      }
    }

    const svg = root.attr("viewBox", `0 0 ${width} ${height}`).attr("role", "img");
    const group = svg.append("g");
    svg.call(d3.zoom().scaleExtent([0.7, 3]).on("zoom", (event) => group.attr("transform", event.transform)));

    const simulation = d3
      .forceSimulation([...nodesById.values()])
      .force("link", d3.forceLink(links).id((node) => node.id).distance(90))
      .force("charge", d3.forceManyBody().strength(-180))
      .force("center", d3.forceCenter(width / 2, height / 2));

    const link = group.selectAll("line").data(links).join("line").attr("stroke", "var(--mist)").attr("stroke-opacity", 0.55);
    const node = group
      .selectAll("circle")
      .data([...nodesById.values()])
      .join("circle")
      .attr("r", (nodeData) => 8 + Math.min(12, nodeData.count * 2))
      .attr("fill", (nodeData) => (nodeData.followed ? "var(--iris)" : "transparent"))
      .attr("stroke", (nodeData) => (nodeData.followed ? "var(--neon)" : "var(--rose)"))
      .attr("stroke-width", 2)
      .style("filter", "drop-shadow(0 0 12px rgba(124,58,237,.35))")
      .call(
        d3
          .drag()
          .on("start", (event) => {
            if (!event.active) simulation.alphaTarget(0.3).restart();
            event.subject.fx = event.subject.x;
            event.subject.fy = event.subject.y;
          })
          .on("drag", (event) => {
            event.subject.fx = event.x;
            event.subject.fy = event.y;
          })
          .on("end", (event) => {
            if (!event.active) simulation.alphaTarget(0);
            event.subject.fx = null;
            event.subject.fy = null;
          }),
      );

    const label = group
      .selectAll("text")
      .data([...nodesById.values()])
      .join("text")
      .text((nodeData) => nodeData.id)
      .attr("font-size", 11)
      .attr("fill", "var(--snow)")
      .attr("paint-order", "stroke")
      .attr("stroke", "var(--void)")
      .attr("stroke-width", 4);

    node.on("mouseenter", (_, hovered) => {
      link.attr("stroke", (edge) => (edge.source.id === hovered.id || edge.target.id === hovered.id ? "var(--neon)" : "var(--mist)"));
    });
    node.on("mouseleave", () => link.attr("stroke", "var(--mist)"));

    simulation.on("tick", () => {
      link
        .attr("x1", (edge) => edge.source.x)
        .attr("y1", (edge) => edge.source.y)
        .attr("x2", (edge) => edge.target.x)
        .attr("y2", (edge) => edge.target.y);
      node.attr("cx", (nodeData) => nodeData.x).attr("cy", (nodeData) => nodeData.y);
      label.attr("x", (nodeData) => nodeData.x + 12).attr("y", (nodeData) => nodeData.y + 4);
    });

    return () => simulation.stop();
  }, [tracks]);

  const collabCount = tracks.filter((track) => track.is_collaboration || track.performer_role === "featured").length;
  if (collabCount < 2) {
    return <div className="grid h-[320px] place-items-center text-sm text-comet">Need at least 2 collaboration tracks for the graph.</div>;
  }

  return <svg ref={ref} className="h-[420px] w-full rounded-[20px] bg-void/50" />;
}
