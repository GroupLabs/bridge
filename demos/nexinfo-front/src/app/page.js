"use client";

import Link from "next/link";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/ui/select";
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  CardFooter,
} from "@/components/ui/card";
import nexinfo from "@/app/nexinfo.png";
import Image from "next/image";
import React, { useState, useEffect } from "react";
import { HoverBorderGradient } from "@/components/ui/hover-border-gradient";

import { CountryDropdown, RegionDropdown } from "react-country-region-selector";

export default function Home() {
  const [country, setCountry] = useState("");
  const [region, setRegion] = useState("");
  const [selectedTime, setSelectedTime] = useState("all");

  const handleCountryChange = (val) => {
    setCountry(val);
    if (val === "") {
      setRegion("");
    }
  };

  const [cardsData, setCardsData] = useState([]);

  const [searchInput, setSearchInput] = useState("");

  useEffect(() => {
    // Fetch data from /api/search
    fetch("/api/search")
      .then((response) => response.json())
      .then((data) => {
        setCardsData(data);
      })
      .catch((error) => console.error("Error fetching data:", error));
  }, []);

  const filteredCardData = cardsData.filter((card) => {
    const isTimeMatch =
      selectedTime === "all" || card.monthsAgo <= parseInt(selectedTime);
    const isCountryMatch = country === "" || card.country === country;
    const isRegionMatch = region === "" || card.region === region;
    const searchText = searchInput.toLowerCase();
    const doesTextMatch =
      !searchText ||
      card.name.toLowerCase().includes(searchText) ||
      card.title.toLowerCase().includes(searchText) ||
      card.description.toLowerCase().includes(searchText) ||
      card.country.toLowerCase().includes(searchText) ||
      card.region.toLowerCase().includes(searchText);
    return isTimeMatch && isCountryMatch && isRegionMatch && doesTextMatch;
  });

  return (
    <div className="flex flex-col items-center w-full min-h-screen bg-background lg:pt-24">
      <header className="flex flex-col lg:flex-row items-center justify-between w-full max-w-6xl px-4 py-6 lg:px-6">
        <Link
          href="#"
          prefetch={false}
          className="flex items-center mb-4 lg:mb-0"
        >
          <Image
            src={nexinfo}
            alt={`nextinfo logo`}
            className="w-80"
            priority={true}
          />
          <span className="sr-only">NEXINFO</span>
        </Link>
        <div className="flex flex-col items-center gap-4 w-full max-w-2xl">
          <Input
            placeholder="Search for company requirements..."
            className="w-full"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
          />
          <div className="w-full flex flex-col lg:flex-row items-center justify-between w-full gap-4 lg:gap-0">
            <div className="w-full flex flex-col lg:flex-row items-center gap-2">
              <Label htmlFor="location" className="text-sm">
                Location
              </Label>
              <CountryDropdown
                defaultOptionLabel="All countries"
                blankOptionLabel="All countries"
                className="pl-1 h-10 w-full lg:w-40 rounded-md border border-input bg-background text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 [&>span]:line-clamp-1"
                value={country}
                onChange={(val) => handleCountryChange(val)}
              />
              <RegionDropdown
                defaultOptionLabel="All regions"
                disableWhenEmpty={true}
                className="pl-1 h-10 w-full lg:w-40 rounded-md border border-input bg-background text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 [&>span]:line-clamp-1"
                country={country}
                value={region}
                onChange={(val) => setRegion(val)}
              />
            </div>
            <div className="flex flex-col lg:flex-row items-center gap-2 w-full lg:pl-4">
              <Label htmlFor="date" className="text-sm">
                Date of listing
              </Label>
              <Select
                id="date"
                defaultValue="all"
                className="w-full lg:w-40"
                onValueChange={(val) => setSelectedTime(val)}
              >
                <SelectTrigger className="w-full lg:w-40 px-0 pl-2">
                  <SelectValue placeholder="All" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All</SelectItem>
                  <SelectItem value="1">1 month</SelectItem>
                  <SelectItem value="3">3 months</SelectItem>
                  <SelectItem value="6">6 months</SelectItem>
                  <SelectItem value="12">12 months</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </div>
      </header>

      <main className="grid gap-8 w-full max-w-6xl px-4 py-8 lg:px-6">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {filteredCardData.map((card, index) => (
            <HoverBorderGradient>
              <Card key={index} className="min-h-52 rounded-[22px] w-full">
                <CardHeader>
                  <CardTitle>
                    <p>{card.name}</p>
                    <p>{card.title}</p>
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <p>{card.description}</p>
                </CardContent>
                <CardFooter>
                  <div className="flex items-center justify-between">
                    <div className="text-sm text-muted-foreground">
                      <p className="font-semibold">
                        {card.region && card.country
                          ? `${card.region}, ${card.country}`
                          : card.region || card.country}
                      </p>
                      <p>
                        {card.monthsAgo} month{card.monthsAgo > 1 ? "s" : ""}{" "}
                        ago
                      </p>
                      <a href={card.url}>{card.url}</a>
                    </div>
                  </div>
                </CardFooter>
              </Card>
            </HoverBorderGradient>
          ))}
        </div>
      </main>
    </div>
  );
}
