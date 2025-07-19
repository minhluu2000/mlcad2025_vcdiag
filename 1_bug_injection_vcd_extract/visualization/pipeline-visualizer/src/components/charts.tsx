import React from "react";
import { PieChart, Pie, Cell, Tooltip, BarChart, Bar, XAxis, YAxis, CartesianGrid, RadialBarChart, RadialBar, ResponsiveContainer, PolarAngleAxis } from "recharts";

const PRIMARY_COLOR = "#807d54";
const TEXT_COLOR = "#374151";
const BG_COLOR = "#242424";

interface ChartData {
  name: string;
  amount: number;
}

interface ChartProps {
  data: ChartData[];
  height: number;
  title: string;
}

// Pie Chart Component
export const PieChartComponent: React.FC<ChartProps> = ({ data, height, title }) => {
  return (
    <div style={{ width: height, height: height, textAlign: "center" }}>
      <ResponsiveContainer width={"100%"} height={"100%"}>
        <PieChart>
          <Pie data={data} dataKey="amount" nameKey="name" cx="50%" cy="50%" outerRadius={100} fill={PRIMARY_COLOR} label>
            {data.map((_, index) => (
              <Cell key={`cell-${index}`} fill={PRIMARY_COLOR} />
            ))}
          </Pie>
          <Tooltip />
        </PieChart>
      </ResponsiveContainer>
      <div style={{ color: TEXT_COLOR, marginTop: "10px", fontSize: "16px", fontWeight: "bold" }}>{title}</div>
    </div>
  );
};

// Bar Chart Component
export const BarChartComponent: React.FC<ChartProps> = ({ data, height, title }) => {
  return (
    <div style={{ flex: 2, width: height, height: height, display: "flex", flexDirection: "column", justifyContent: "center" }}>
      <div style={{ width: "100%", height: 0.8 * height }}>
        <ResponsiveContainer width={"100%"} height={"100%"}>
          <BarChart data={data} layout="vertical">
            <CartesianGrid strokeDasharray="3 3" stroke={TEXT_COLOR} />
            <XAxis type="number" stroke={TEXT_COLOR} />
            <YAxis dataKey="name" type="category" stroke={TEXT_COLOR} width={150} />
            <Tooltip />
            <Bar dataKey="amount" fill={PRIMARY_COLOR} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <div style={{ color: TEXT_COLOR, marginTop: "10px", fontSize: "16px", fontWeight: "bold", textAlign: "center" }}>{title}</div>
    </div>
  );
};

// Radial Progress Indicator
export const RadialProgress: React.FC<{ percentage: number; height: number; title: string }> = ({ percentage, height, title }) => {
  const data = [{ name: "Progress", amount: percentage }];
  return (
    <div style={{ width: height * 0.8, height: height * 0.8, textAlign: "center" }}>
      <ResponsiveContainer width={"100%"} height={"100%"}>
        <RadialBarChart
          cx="50%"
          cy="50%"
          innerRadius="80%"
          outerRadius="100%"
          startAngle={-270}
          endAngle={90}
          barSize={15}
          data={data}
        >
          <PolarAngleAxis type="number" domain={[0, 100]} angleAxisId={0} tick={false} />
          <RadialBar dataKey="amount" fill={PRIMARY_COLOR} />
          <text x="50%" y="50%" dy={8} textAnchor="middle" fill={TEXT_COLOR} style={{ fontSize: "20px", fontWeight: "bold" }}>
            {Math.round(percentage * 10) / 10}%
          </text>
        </RadialBarChart>
      </ResponsiveContainer>
      <div style={{ color: TEXT_COLOR, marginTop: "10px", fontSize: "16px", fontWeight: "bold" }}>{title}</div>
    </div>
  );
};
